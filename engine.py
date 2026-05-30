import os
import json
import time
import threading
from btree import BTree
from storage import TableStorage
from wal import WriteAheadLog
from parser import QueryParser

class DatabaseEngine:
    """
    Glues together the B-Tree index, TableStorage, WAL, and query execution logic.
    """
    def __init__(self, db_dir):
        self.db_dir = db_dir
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        self.tables = {}
        self.indexes = {}
        self.schemas = {}
        self.undo_stack = []
        self.redo_stack = []
        self.transaction_checkpoint = None
        
        # Initialize WAL and perform crash recovery BEFORE loading normal operations
        self.wal = WriteAheadLog(os.path.join(self.db_dir, "essadb.wal"))
        self.parser = QueryParser()
        
        self.row_locks = {}
        self.lock_manager_lock = threading.Lock()
        
        self._load_meta()
        self._recover_from_wal()
        
        if "_edges" not in self.tables:
            self.execute(self.parser.parse("CREATE TABLE _edges (id INT, src_table STR, src_id INT, tgt_table STR, tgt_id INT, edge_type STR)"))

    def _acquire_row_lock(self, table_name, offset):
        key = (table_name, offset)
        with self.lock_manager_lock:
            if key not in self.row_locks:
                self.row_locks[key] = threading.Lock()
        self.row_locks[key].acquire()

    def _release_row_lock(self, table_name, offset):
        key = (table_name, offset)
        with self.lock_manager_lock:
            if key in self.row_locks:
                self.row_locks[key].release()

    def _recover_from_wal(self):
        uncommitted = self.wal.get_uncommitted_transactions()
        if uncommitted:
            print(f"\n[WAL RECOVERY] Found {len(uncommitted)} crashed transactions. Replaying to guarantee Durability...")
            for query in uncommitted:
                try:
                    self.execute(query, is_recovery=True)
                except Exception as e:
                    print(f"Failed to recover query {query}: {e}")
        
        # Checkpoint WAL (clear it now that all data is safely in .dat and .idx)
        self.wal.clear()

    def _load_meta(self):
        meta_path = os.path.join(self.db_dir, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                self.schemas = json.load(f)
                
        idx_meta_path = os.path.join(self.db_dir, "indexes.json")
        self.secondary_index_meta = {}
        if os.path.exists(idx_meta_path):
            with open(idx_meta_path, 'r') as f:
                self.secondary_index_meta = json.load(f)
                
        fk_meta_path = os.path.join(self.db_dir, "fks.json")
        self.foreign_keys = {}
        if os.path.exists(fk_meta_path):
            with open(fk_meta_path, 'r') as f:
                self.foreign_keys = json.load(f)
                
        views_meta_path = os.path.join(self.db_dir, "views.json")
        self.views = {}
        if os.path.exists(views_meta_path):
            with open(views_meta_path, 'r') as f:
                self.views = json.load(f)
                
        triggers_meta_path = os.path.join(self.db_dir, "triggers.json")
        self.triggers = {}
        if os.path.exists(triggers_meta_path):
            with open(triggers_meta_path, 'r') as f:
                self.triggers = json.load(f)
            
        for table_name, schema in self.schemas.items():
            storage = TableStorage(os.path.join(self.db_dir, f"{table_name}.dat"), schema)
            self.tables[table_name] = storage
            self._build_index(table_name)

    def _save_meta(self):
        meta_path = os.path.join(self.db_dir, "meta.json")
        with open(meta_path, 'w') as f:
            json.dump(self.schemas, f)

    def _build_index(self, table_name):
        schema = self.schemas[table_name]
        
        if table_name not in self.indexes:
            self.indexes[table_name] = {}
            
        # Primary Key index
        pk_col_name = schema[0][0]
        idx_path = os.path.join(self.db_dir, f"{table_name}.idx")
        b_tree = self._init_btree_file(idx_path, table_name, 0)
        self.indexes[table_name][pk_col_name] = b_tree
        
        # Secondary indexes
        for col_name in self.secondary_index_meta.get(table_name, []):
            col_idx = self._get_col_idx(schema, col_name)
            if col_idx != -1:
                idx_path = os.path.join(self.db_dir, f"{table_name}_{col_name}.idx")
                b_tree = self._init_btree_file(idx_path, table_name, col_idx)
                self.indexes[table_name][col_name] = b_tree

    def _init_btree_file(self, idx_path, table_name, col_idx):
        index_exists = os.path.exists(idx_path)
        b_tree = BTree(idx_path, t=50)
        storage = self.tables[table_name]
        if not index_exists:
            records, offsets = storage.read_all()
            for rec, offset in zip(records, offsets):
                b_tree.insert(rec[col_idx], offset)
        return b_tree

    def execute(self, parsed_query, is_recovery=False):
        q_type = parsed_query["type"]
        
        # Read operations bypass the WAL
        if q_type == "SELECT":
            return self._execute_select(parsed_query)
        elif q_type == "SHOW_TABLES":
            return self._execute_show_tables()
        elif q_type == "DESCRIBE":
            return self._execute_describe(parsed_query)
        
        if q_type == "BEGIN":
            if self.transaction_checkpoint is not None:
                return "Error: Transaction already in progress."
            self.transaction_checkpoint = len(self.undo_stack)
            return "Transaction started."
            
        elif q_type == "COMMIT":
            if self.transaction_checkpoint is None:
                return "Error: No active transaction."
            self.transaction_checkpoint = None
            
            # Flush Buffer Pool for all trees
            for table_indexes in self.indexes.values():
                for b_tree in table_indexes.values():
                    b_tree.flush()
                
            return "Transaction committed."
            
        elif q_type == "ROLLBACK":
            if self.transaction_checkpoint is None:
                return "Error: No active transaction."
            rolled_back_count = 0
            while len(self.undo_stack) > self.transaction_checkpoint:
                self._execute_undo()
                rolled_back_count += 1
            self.transaction_checkpoint = None
            return f"Transaction rolled back. {rolled_back_count} operation(s) reversed."

        if q_type == "UNDO":
            return self._execute_undo()
        elif q_type == "REDO":
            return self._execute_redo()
        elif q_type == "VACUUM":
            return self._execute_vacuum(parsed_query)

        # Write operations go through the WAL (unless we are replaying the WAL during recovery)
        tx_id = None
        if not is_recovery and q_type not in ("UNDO", "REDO", "SHOW_TABLES", "DESCRIBE") and not parsed_query.get("explain"):
            if q_type in ("INSERT", "UPDATE", "DELETE", "CREATE_EDGE"):
                tx_id = self.wal.begin_transaction(parsed_query)
            
        result = None
        if q_type == "CREATE":
            if parsed_query.get("explain"): return "EXPLAIN PLAN: Create Table and B-Tree files."
            result = self._execute_create(parsed_query)
        elif q_type == "CREATE_INDEX":
            if parsed_query.get("explain"): return "EXPLAIN PLAN: Create Secondary B-Tree Index."
            result = self._execute_create_index(parsed_query)
        elif q_type == "CREATE_VIEW":
            self.views[parsed_query["view_name"]] = parsed_query["select_query"]
            with open(os.path.join(self.db_dir, "views.json"), 'w') as f:
                json.dump(self.views, f)
            result = f"View '{parsed_query['view_name']}' created successfully."
        elif q_type == "CREATE_TRIGGER":
            t_name = parsed_query["table"]
            event = parsed_query["event"]
            timing = parsed_query["timing"]
            
            if t_name not in self.triggers: self.triggers[t_name] = {}
            if event not in self.triggers[t_name]: self.triggers[t_name][event] = {}
            if timing not in self.triggers[t_name][event]: self.triggers[t_name][event][timing] = []
            
            self.triggers[t_name][event][timing].append({
                "name": parsed_query["trigger_name"],
                "action": parsed_query["action"]
            })
            with open(os.path.join(self.db_dir, "triggers.json"), 'w') as f:
                json.dump(self.triggers, f)
            result = f"Trigger '{parsed_query['trigger_name']}' created successfully."
        elif q_type == "CREATE_EDGE":
            result = self._execute_create_edge(parsed_query, is_recovery=is_recovery)
        elif q_type == "MATCH":
            result = self._execute_match(parsed_query)
        elif q_type == "INSERT":
            result = self._execute_insert(parsed_query, is_recovery=is_recovery)
        elif q_type == "DELETE":
            result = self._execute_delete(parsed_query, is_recovery=is_recovery)
        elif q_type == "UPDATE":
            result = self._execute_update(parsed_query, is_recovery=is_recovery)

        # After successfully applying to DB files, commit the transaction
        if not is_recovery and tx_id:
            # Flush Buffer Pool to ensure physical durability before WAL commit!
            for table_indexes in self.indexes.values():
                for b_tree in table_indexes.values():
                    b_tree.flush()
            self.wal.commit_transaction(tx_id)
            
        return result

    def _execute_show_tables(self):
        if not self.schemas:
            return "No tables found."
        return [[t] for t in self.schemas.keys()]

    def _execute_describe(self, query):
        table_name = query["table"]
        if table_name not in self.schemas:
            return f"Error: Table '{table_name}' does not exist."
        return [[col_name, dtype] for col_name, dtype in self.schemas[table_name]]

    def _execute_undo(self):
        if not self.undo_stack:
            return "Nothing to UNDO."
        action = self.undo_stack.pop()
        
        if action["type"] == "INSERT":
            storage = self.tables[action["table"]]
            storage.delete_record(action["offset"])
            self.redo_stack.append(action)
            return "Undo INSERT successful."
            
        elif action["type"] == "DELETE":
            storage = self.tables[action["table"]]
            for offset in action["offsets"]:
                storage.undelete_record(offset)
            self.redo_stack.append(action)
            return "Undo DELETE successful."
            
        elif action["type"] == "UPDATE":
            storage = self.tables[action["table"]]
            for offset, old_rec in action["old_records"]:
                storage.update_record(offset, old_rec)
            self.redo_stack.append(action)
            return "Undo UPDATE successful."

    def _execute_redo(self):
        if not self.redo_stack:
            return "Nothing to REDO."
        action = self.redo_stack.pop()
        
        if action["type"] == "INSERT":
            storage = self.tables[action["table"]]
            storage.undelete_record(action["offset"])
            self.undo_stack.append(action)
            return "Redo INSERT successful."
            
        elif action["type"] == "DELETE":
            storage = self.tables[action["table"]]
            for offset in action["offsets"]:
                storage.delete_record(offset)
            self.undo_stack.append(action)
            return "Redo DELETE successful."
            
        elif action["type"] == "UPDATE":
            storage = self.tables[action["table"]]
            for offset, new_rec in action["new_records"]:
                storage.update_record(offset, new_rec)
            self.undo_stack.append(action)
            return "Redo UPDATE successful."

    def _execute_vacuum(self, query):
        table_name = query["table"]
        if table_name not in self.tables:
            return f"Error: Table '{table_name}' does not exist."
            
        storage = self.tables[table_name]
        records, _ = storage.read_all()
        schema = self.schemas[table_name]
        
        # 1. Write to temporary files
        tmp_dat_path = os.path.join(self.db_dir, f"{table_name}_vacuum.dat")
        if os.path.exists(tmp_dat_path): os.remove(tmp_dat_path)
        tmp_storage = TableStorage(tmp_dat_path, schema)
        
        tmp_btrees = {}
        for col_name in self.indexes[table_name].keys():
            idx_path = os.path.join(self.db_dir, f"{table_name}_{col_name}_vacuum.idx")
            if os.path.exists(idx_path): os.remove(idx_path)
            tmp_btrees[col_name] = BTree(idx_path, t=50)
        
        for rec in records:
            offset = tmp_storage.insert_record(rec)
            for col_name, b_tree in tmp_btrees.items():
                col_idx = self._get_col_idx(schema, col_name)
                b_tree.insert(rec[col_idx], offset)
            
        tmp_storage.close()
        for b_tree in tmp_btrees.values(): b_tree.close()
        
        # 2. Swap files safely
        storage.close()
        for b_tree in self.indexes[table_name].values(): b_tree.close()
        
        dat_path = os.path.join(self.db_dir, f"{table_name}.dat")
        os.remove(dat_path)
        os.rename(tmp_dat_path, dat_path)
        
        pk_col_name = schema[0][0]
        for col_name in tmp_btrees.keys():
            tmp_idx_path = os.path.join(self.db_dir, f"{table_name}_{col_name}_vacuum.idx")
            if col_name == pk_col_name:
                idx_path = os.path.join(self.db_dir, f"{table_name}.idx")
            else:
                idx_path = os.path.join(self.db_dir, f"{table_name}_{col_name}.idx")
            if os.path.exists(idx_path): os.remove(idx_path)
            os.rename(tmp_idx_path, idx_path)
        
        # 3. Re-open storage and indices
        self.tables[table_name] = TableStorage(dat_path, schema)
        self.indexes.pop(table_name, None)
        self._build_index(table_name)
        
        # 4. Invalidate undo/redo stacks since physical offsets have completely changed
        self.undo_stack.clear()
        self.redo_stack.clear()
        
        return f"VACUUM successful. Recovered disk space and defragmented '{table_name}'."

    def _run_triggers(self, table_name, event, timing, old_rec=None, new_rec=None, schema=None):
        if table_name not in self.triggers: return
        actions = self.triggers[table_name].get(event, {}).get(timing, [])
        for trigger in actions:
            action_str = trigger["action"]
            if schema:
                for i, (col, _) in enumerate(schema):
                    if new_rec:
                        val = str(new_rec[i]) if not isinstance(new_rec[i], str) else f"'{new_rec[i]}'"
                        action_str = action_str.replace(f"NEW.{col}", val)
                    if old_rec:
                        val = str(old_rec[i]) if not isinstance(old_rec[i], str) else f"'{old_rec[i]}'"
                        action_str = action_str.replace(f"OLD.{col}", val)
            
            try:
                parsed_action = self.parser.parse(action_str)
                self.execute(parsed_action)
            except Exception as e:
                print(f"Trigger {trigger['name']} failed: {e}")

    def _execute_create(self, query):
        table_name = query["table"]
        columns = query["columns"]
        foreign_keys = query.get("foreign_keys", [])
        
        if table_name in self.schemas:
            return f"Table '{table_name}' already exists."
            
        if foreign_keys:
            for fk in foreign_keys:
                if fk["ref_table"] not in self.schemas:
                    return f"Error: Referenced table '{fk['ref_table']}' does not exist."
            self.foreign_keys[table_name] = foreign_keys
            
            fk_meta_path = os.path.join(self.db_dir, "fks.json")
            with open(fk_meta_path, 'w') as f:
                json.dump(self.foreign_keys, f)
        
        self.schemas[table_name] = columns
        storage = TableStorage(os.path.join(self.db_dir, f"{table_name}.dat"), columns)
        self.tables[table_name] = storage
        self._save_meta()
        self._build_index(table_name)
        return f"Table '{table_name}' created successfully."

    def _execute_create_index(self, query):
        table_name = query["table"]
        col_name = query["col"]
        idx_name = query["index_name"]
        
        if table_name not in self.tables:
            return f"Error: Table '{table_name}' does not exist."
            
        schema = self.schemas[table_name]
        col_idx = self._get_col_idx(schema, col_name)
        if col_idx == -1:
            return f"Error: Column '{col_name}' does not exist."
            
        if table_name not in self.secondary_index_meta:
            self.secondary_index_meta[table_name] = []
            
        if col_name in self.secondary_index_meta[table_name] or col_name == schema[0][0]:
            return f"Error: Index on '{col_name}' already exists."
            
        self.secondary_index_meta[table_name].append(col_name)
        
        # Save meta
        idx_meta_path = os.path.join(self.db_dir, "indexes.json")
        with open(idx_meta_path, 'w') as f:
            json.dump(self.secondary_index_meta, f)
            
        # Build it dynamically
        idx_path = os.path.join(self.db_dir, f"{table_name}_{col_name}.idx")
        b_tree = self._init_btree_file(idx_path, table_name, col_idx)
        self.indexes[table_name][col_name] = b_tree
        
        return f"Index '{idx_name}' created on '{table_name}({col_name})'."

    def _execute_insert(self, query, is_recovery=False):
        table_name = query["table"]
        
        if query.get("explain"):
            plan = f"EXPLAIN PLAN FOR INSERT on '{table_name}'\n"
            plan += f"-> Step 1: O(1) Append row to .dat file\n"
            plan += f"-> Step 2: O(log N) Insert node into {len(self.indexes.get(table_name, {}))} B-Tree(s)\n"
            plan += f"-> Step 3: Write to Undo Log"
            return plan
            
        values = query["values"]
        if table_name not in self.tables:
            return f"Error: Table '{table_name}' does not exist."
        
        schema = self.schemas[table_name]
        if len(values) != len(schema):
            return f"Error: Expected {len(schema)} values, got {len(values)}."

        # Primary Key Uniqueness Constraint
        pk_col_name = schema[0][0]
        pk_tree = self.indexes[table_name][pk_col_name]
        key = values[0]
        
        existing_offset = pk_tree.search(key)
        if existing_offset is not None:
            storage = self.tables[table_name]
            if storage.read_record(existing_offset) is not None:
                return f"Constraint Error: Primary Key '{key}' already exists."

        # Foreign Key Verification
        if table_name in self.foreign_keys:
            for fk in self.foreign_keys[table_name]:
                col_idx = self._get_col_idx(schema, fk["col"])
                val = values[col_idx]
                
                ref_schema = self.schemas[fk["ref_table"]]
                ref_col_idx = self._get_col_idx(ref_schema, fk["ref_col"])
                
                ref_tree = self.indexes.get(fk["ref_table"], {}).get(fk["ref_col"])
                if ref_tree:
                    if ref_tree.search(val) is None:
                        return f"Constraint Error: Foreign Key '{val}' not found in {fk['ref_table']}({fk['ref_col']})."
                else:
                    ref_storage = self.tables[fk["ref_table"]]
                    records, _ = ref_storage.read_all()
                    found = False
                    for r in records:
                        if r[ref_col_idx] == val:
                            found = True
                            break
                    if not found:
                        return f"Constraint Error: Foreign Key '{val}' not found in {fk['ref_table']}({fk['ref_col']})."

        self._run_triggers(table_name, "INSERT", "BEFORE", new_rec=values, schema=schema)

        storage = self.tables[table_name]
        offset = storage.insert_record(values)
        
        for col_name, b_tree in self.indexes[table_name].items():
            col_idx = self._get_col_idx(schema, col_name)
            b_tree.insert(values[col_idx], offset)
        
        if not is_recovery:
            self.undo_stack.append({"type": "INSERT", "table": table_name, "offset": offset})
            self.redo_stack.clear()
        
        return "1 row inserted."

    def _apply_aggregations(self, records, combined_schema, targets, group_by_col):
        if len(targets) == 1 and targets[0]["type"] == "ALL" and not group_by_col:
            return records
            
        col_name_to_idx = {name: i for i, (name, _) in enumerate(combined_schema)}
        
        if group_by_col:
            group_idx = col_name_to_idx.get(group_by_col)
            if group_idx is None: return f"Error: GROUP BY column '{group_by_col}' not found."
            
            groups = {}
            for rec in records:
                key = rec[group_idx]
                if key not in groups: groups[key] = []
                groups[key].append(rec)
        else:
            groups = {None: records}
            
        has_agg = any(t["type"] == "AGG" for t in targets)
        
        if not has_agg and not group_by_col:
            # Scalar mapping & Window functions per row
            final_results = []
            win_state = {} # Stores cross-row state for window functions
            
            for rec in records:
                out_row = []
                for target in targets:
                    if target["type"] == "COL":
                        idx = col_name_to_idx.get(target["col"])
                        if idx is None: return f"Error: Column '{target['col']}' not found."
                        out_row.append(rec[idx])
                    elif target["type"] == "FUNC":
                        func = target["func"]
                        col_idx = col_name_to_idx.get(target["col"])
                        if col_idx is None: return f"Error: Column '{target['col']}' not found for function."
                        val = rec[col_idx]
                        if val is not None:
                            if func == "UPPER": val = str(val).upper()
                            elif func == "LOWER": val = str(val).lower()
                            elif func == "LENGTH": val = len(str(val))
                            elif func == "ABS": val = abs(float(val))
                            elif func == "ROUND": val = round(float(val))
                        out_row.append(val)
                    elif target["type"] == "WIN":
                        func = target["func"]
                        col_idx = col_name_to_idx.get(target["col"])
                        if col_idx is None: return f"Error: Column '{target['col']}' not found for window function."
                        
                        val = rec[col_idx]
                        state_key = f"{func}_{target['col']}"
                        
                        if func == "RUNNING_TOTAL":
                            current_total = win_state.get(state_key, 0.0)
                            if isinstance(val, (int, float)):
                                current_total += float(val)
                            win_state[state_key] = current_total
                            out_row.append(current_total)
                            
                        elif func == "LAG":
                            prev_val = win_state.get(state_key, None)
                            win_state[state_key] = val
                            out_row.append(prev_val)
                            
                        elif func == "CUMULATIVE_AVG":
                            current_sum, count = win_state.get(state_key, (0.0, 0))
                            if isinstance(val, (int, float)):
                                current_sum += float(val)
                                count += 1
                            win_state[state_key] = (current_sum, count)
                            out_row.append(current_sum / count if count > 0 else 0.0)
                final_results.append(tuple(out_row))
            return final_results
            
        final_results = []
        for group_key, group_recs in groups.items():
            out_row = []
            for target in targets:
                if target["type"] == "COL":
                    idx = col_name_to_idx.get(target["col"])
                    if idx is None: return f"Error: Column '{target['col']}' not found."
                    out_row.append(group_recs[0][idx] if group_recs else None)
                elif target["type"] == "FUNC":
                    func = target["func"]
                    col_idx = col_name_to_idx.get(target["col"])
                    if col_idx is None: return f"Error: Column '{target['col']}' not found for function."
                    
                    val = group_recs[0][col_idx] if group_recs else None
                    if val is not None:
                        if func == "UPPER": val = str(val).upper()
                        elif func == "LOWER": val = str(val).lower()
                        elif func == "LENGTH": val = len(str(val))
                        elif func == "ABS": val = abs(float(val))
                        elif func == "ROUND": val = round(float(val))
                    out_row.append(val)
                elif target["type"] == "AGG":
                    func = target["func"]
                    col_idx = col_name_to_idx.get(target["col"])
                    if col_idx is None: return f"Error: Column '{target['col']}' not found for aggregation."
                    
                    vals = [r[col_idx] for r in group_recs]
                    if func == "COUNT":
                        out_row.append(len(vals))
                    elif func == "SUM":
                        out_row.append(sum(vals) if vals else 0.0)
                    elif func == "AVG":
                        out_row.append(sum(vals)/len(vals) if vals else 0.0)
            final_results.append(tuple(out_row))
            
        return final_results

    def _evaluate_conditions(self, record, schema, conditions):
        for cond in conditions:
            col_idx = self._get_col_idx(schema, cond["col"])
            if col_idx == -1: return False
            
            rec_val = record[col_idx]
            val = cond["val"]
            op = cond["op"]
            
            json_key = cond.get("json_key")
            if json_key:
                if isinstance(rec_val, dict):
                    rec_val = rec_val.get(json_key)
                else:
                    return False
            
            if op == "IN":
                if rec_val not in val: return False
                continue
                
            # Type safety
            if type(rec_val) != type(val) and type(rec_val) in (int, float) and type(val) in (int, float):
                val = type(rec_val)(val)
                
            try:
                if op == "=" and not (rec_val == val): return False
                if op == "!=" and not (rec_val != val): return False
                if op == ">" and not (rec_val > val): return False
                if op == "<" and not (rec_val < val): return False
                if op == ">=" and not (rec_val >= val): return False
                if op == "<=" and not (rec_val <= val): return False
            except TypeError:
                return False
        return True

    def _get_query_schema(self, query):
        table_name = query["table"]
        base_schema = self.schemas.get(table_name, [])
        targets = query.get("targets", [{"type": "ALL"}])
        if len(targets) == 1 and targets[0]["type"] == "ALL":
            return base_schema
        out_schema = []
        for t in targets:
            if t["type"] == "COL":
                dtype = "STR"
                for n, d in base_schema:
                    if n == t["col"]: dtype = d; break
                out_schema.append((t["col"], dtype))
        return out_schema

    def _execute_select(self, query):
        if query.get("join_table"):
            return self._execute_join(query)
            
        table_name = query["table"]
        conditions = query.get("conditions", [])

        # Evaluate Subqueries and NOW() once before row filtering
        for cond in conditions:
            if cond["op"] == "IN" and "subquery" in cond:
                sub_parsed = self.parser.parse(cond["subquery"])
                sub_results = self.execute(sub_parsed)
                cond["val"] = [r[0] for r in sub_results]
            elif isinstance(cond["val"], str) and cond["val"].upper() == 'NOW()':
                from datetime import datetime
                cond["val"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Virtual View Support
        if table_name in self.views:
            view_query_str = self.views[table_name]
            view_parsed = self.parser.parse(view_query_str)
            records = self.execute(view_parsed)
            schema = self._get_query_schema(view_parsed)
            result_records = [rec for rec in records if self._evaluate_conditions(rec, schema, conditions)]
            idx_cond = None
        else:
            if table_name not in self.tables:
                return f"Error: Table '{table_name}' does not exist."
    
            storage = self.tables[table_name]
            schema = self.schemas[table_name]
    
            # Query Optimizer: Pick the best index
            idx_cond = None
            best_b_tree = None
            for cond in conditions:
                if cond["op"] == "=" and cond["col"] in self.indexes.get(table_name, {}):
                    idx_cond = cond
                    best_b_tree = self.indexes[table_name][cond["col"]]
                    break
    
            if query.get("explain"):
                plan = f"EXPLAIN PLAN FOR SELECT on '{table_name}'\n"
                if idx_cond:
                    plan += f"-> Strategy: Index Condition Pushdown (B-Tree on '{idx_cond['col']}')\n"
                    plan += f"-> Step 1: O(log N) Index Scan on '{idx_cond['col']}' for value '{idx_cond['val']}'\n"
                    if len(conditions) > 1:
                        plan += f"-> Step 2: O(1) In-memory filter on remaining {len(conditions)-1} condition(s)"
                    else:
                        plan += "-> Step 2: No further filtering needed"
                else:
                    plan += f"-> Strategy: Full Table Scan\n"
                    plan += f"-> Step 1: O(N) Sequential read on '{table_name}'\n"
                    if conditions:
                        plan += f"-> Step 2: O(N) In-memory filter on {len(conditions)} condition(s)"
                return plan
    
            if idx_cond:
                offset = best_b_tree.search(idx_cond["val"])
                if offset is not None:
                    rec = storage.read_record(offset)
                    if rec and self._evaluate_conditions(rec, schema, conditions):
                        result_records = [rec]
                    else:
                        result_records = []
                else:
                    result_records = []
            else:
                records, _ = storage.read_all()
                result_records = [rec for rec in records if self._evaluate_conditions(rec, schema, conditions)]

        order_by = query.get("order_by")
        if order_by:
            if order_by.get("type") == "SIMILARITY":
                col_name = order_by["col"]
                target_vec = order_by["vector"]
                col_idx = self._get_col_idx(schema, col_name)
                if col_idx != -1:
                    result_records.sort(key=lambda x: self._cosine_similarity(x[col_idx], target_vec), reverse=(order_by["dir"] == "DESC"))
            else:
                col_name = order_by["col"]
                col_idx = self._get_col_idx(schema, col_name)
                if col_idx != -1:
                    result_records.sort(key=lambda x: x[col_idx], reverse=(order_by["dir"] == "DESC"))

        targets = query.get("targets", [{"type": "ALL"}])
        group_by = query.get("group_by")
        final_results = self._apply_aggregations(result_records, schema, targets, group_by)
        
        limit = query.get("limit")
        if limit is not None:
            final_results = final_results[:limit]
            
        return final_results

    def _cosine_similarity(self, v1, v2):
        if not v1 or not v2 or not isinstance(v1, list) or not isinstance(v2, list): return 0
        import math
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        return dot / (norm1 * norm2) if norm1 and norm2 else 0

    def _execute_create_edge(self, query, is_recovery=False):
        import random
        edge_id = random.randint(1, 2000000000)
        insert_q = {
            "type": "INSERT",
            "table": "_edges",
            "values": (edge_id, query["source_table"], query["source_id"], query["target_table"], query["target_id"], query["edge_type"])
        }
        return self._execute_insert(insert_q, is_recovery)

    def _execute_match(self, query):
        src_table = query["source_table"]
        edge_type = query["edge_type"]
        tgt_table = query["target_table"]
        conditions = query.get("conditions", [])
        
        src_select = {"type": "SELECT", "table": src_table, "conditions": conditions}
        src_nodes = self._execute_select(src_select)
        
        if not src_nodes:
            return []
            
        src_schema = self.schemas.get(src_table)
        if not src_schema: return []
        src_id_idx = self._get_col_idx(src_schema, "id")
        if src_id_idx == -1: return []
        src_ids = [n[src_id_idx] for n in src_nodes]
        
        edges, _ = self.tables["_edges"].read_all()
        tgt_ids = []
        for e in edges:
            if e[1] == src_table and e[2] in src_ids and e[5] == edge_type and e[3] == tgt_table:
                tgt_ids.append(e[4])
                
        if not tgt_ids:
            return []
            
        tgt_select = {
            "type": "SELECT", 
            "table": tgt_table, 
            "conditions": [{"col": "id", "op": "IN", "val": tgt_ids}]
        }
        return self._execute_select(tgt_select)

    def _execute_join(self, query):
        t1_name = query["table"]
        t2_name = query["join_table"]
        t1_col = query["join_left_col"]
        t2_col = query["join_right_col"]
        
        # Correctly align columns based on table names provided in ON clause
        if query["join_left_tbl"] == t2_name and query["join_right_tbl"] == t1_name:
            t1_col, t2_col = t2_col, t1_col
        elif query["join_left_tbl"] != t1_name or query["join_right_tbl"] != t2_name:
            return "Error: JOIN ON clause must reference the two tables being joined."
            
        if t1_name not in self.tables or t2_name not in self.tables:
            return "Error: One of the tables does not exist."
            
        t1_storage = self.tables[t1_name]
        t2_storage = self.tables[t2_name]
        t1_schema = self.schemas[t1_name]
        t2_schema = self.schemas[t2_name]
        
        t1_col_idx = self._get_col_idx(t1_schema, t1_col)
        t2_col_idx = self._get_col_idx(t2_schema, t2_col)
        
        if t1_col_idx == -1 or t2_col_idx == -1:
            return "Error: Invalid column in JOIN ON clause."

        if query.get("explain"):
            return (
                f"EXPLAIN PLAN FOR HASH JOIN on '{t1_name}' and '{t2_name}'\n"
                f"-> Step 1: O(N) Stream '{t1_name}' and apply {len(query.get('conditions', []))} filter condition(s)\n"
                f"-> Step 2: O(N) Build In-Memory Hash Map using '{t1_name}.{t1_col}'\n"
                f"-> Step 3: O(M) Stream '{t2_name}' and probe Hash Map using '{t2_name}.{t2_col}'\n"
                f"-> Step 4: O(1) Yield combined records"
            )
            
        # 1. Filter Table 1
        t1_records, _ = t1_storage.read_all()
        t1_filtered = []
        for rec in t1_records:
            if self._evaluate_conditions(rec, t1_schema, query.get("conditions", [])):
                t1_filtered.append(rec)
                
        # 2. Build Hash Map for Table 1
        hash_map = {}
        for rec in t1_filtered:
            val = rec[t1_col_idx]
            if val not in hash_map:
                hash_map[val] = []
            hash_map[val].append(rec)
            
        # 3. Stream Table 2 and probe Hash Map
        result_records = []
        t2_records, _ = t2_storage.read_all()
        for t2_rec in t2_records:
            t2_val = t2_rec[t2_col_idx]
            if t2_val in hash_map:
                for t1_rec in hash_map[t2_val]:
                    # Stitch tuples together
                    result_records.append(t1_rec + t2_rec)
                    
        combined_schema = [(f"{t1_name}.{c}", t) for c, t in t1_schema] + \
                          [(f"{t2_name}.{c}", t) for c, t in t2_schema]
        
        order_by = query.get("order_by")
        if order_by:
            col_name = order_by["col"]
            col_idx = self._get_col_idx(combined_schema, col_name)
            if col_idx != -1:
                result_records.sort(key=lambda x: x[col_idx], reverse=(order_by["dir"] == "DESC"))
                
        targets = query.get("targets", [{"type": "ALL"}])
        group_by = query.get("group_by")
        
        if len(targets) == 1 and targets[0]["type"] == "ALL" and not group_by:
            final_results = result_records
        else:
            final_results = self._apply_aggregations(result_records, combined_schema, targets, group_by)
            
        limit = query.get("limit")
        if limit is not None:
            final_results = final_results[:limit]
            
        return final_results

    def _execute_delete(self, query, is_recovery=False):
        table_name = query["table"]
        conditions = query.get("conditions", [])

        if table_name not in self.tables:
            return f"Error: Table '{table_name}' does not exist."

        storage = self.tables[table_name]
        schema = self.schemas[table_name]
        
        # Query Optimizer: Pick the best index
        idx_cond = None
        best_b_tree = None
        for cond in conditions:
            if cond["op"] == "=" and cond["col"] in self.indexes.get(table_name, {}):
                idx_cond = cond
                best_b_tree = self.indexes[table_name][cond["col"]]
                break

        if query.get("explain"):
            plan = f"EXPLAIN PLAN FOR DELETE on '{table_name}'\n"
            if idx_cond:
                plan += f"-> Strategy: Index Condition Pushdown (B-Tree on '{idx_cond['col']}')\n"
                plan += f"-> Step 1: O(log N) Index Scan on '{idx_cond['col']}' for value '{idx_cond['val']}'\n"
            else:
                plan += f"-> Strategy: Full Table Scan\n"
                plan += f"-> Step 1: O(N) Sequential read on '{table_name}'\n"
            plan += f"-> Step 2: O(1) Tombstone flip (mark as deleted)\n"
            plan += f"-> Step 3: Write to Undo Log"
            return plan

        deleted_count = 0
        deleted_offsets = []
        deleted_records = []
        
        # Subqueries and NOW() for DELETE
        for cond in conditions:
            if cond["op"] == "IN" and "subquery" in cond:
                sub_parsed = self.parser.parse(cond["subquery"])
                sub_results = self.execute(sub_parsed)
                cond["val"] = [r[0] for r in sub_results]
            elif isinstance(cond["val"], str) and cond["val"].upper() == 'NOW()':
                from datetime import datetime
                cond["val"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        targets = []
        targets_offsets = []
        
        if idx_cond:
            offset = best_b_tree.search(idx_cond["val"])
            if offset is not None:
                rec = storage.read_record(offset)
                if rec and self._evaluate_conditions(rec, schema, conditions):
                    targets.append(rec)
                    targets_offsets.append(offset)
        else:
            records, offsets = storage.read_all()
            for rec, offset in zip(records, offsets):
                if self._evaluate_conditions(rec, schema, conditions):
                    targets.append(rec)
                    targets_offsets.append(offset)
                    
        for offset, rec in zip(targets_offsets, targets):
            self._acquire_row_lock(table_name, offset)
            try:
                self._run_triggers(table_name, "DELETE", "BEFORE", old_rec=rec, schema=schema)
                storage.delete_record(offset)
                deleted_offsets.append(offset)
                deleted_records.append(rec)
                self._run_triggers(table_name, "DELETE", "AFTER", old_rec=rec, schema=schema)
                deleted_count += 1
            finally:
                self._release_row_lock(table_name, offset)
                    
        # Handle Cascading Deletes
        for child_table, fks in self.foreign_keys.items():
            for fk in fks:
                if fk["ref_table"] == table_name and fk["cascade"]:
                    child_schema = self.schemas[child_table]
                    child_col_idx = self._get_col_idx(child_schema, fk["col"])
                    ref_col_idx = self._get_col_idx(schema, fk["ref_col"])
                    
                    for rec in deleted_records:
                        val = rec[ref_col_idx]
                        cascade_query = {
                            "type": "DELETE",
                            "table": child_table,
                            "conditions": [{"col": fk["col"], "op": "=", "val": val}]
                        }
                        self._execute_delete(cascade_query, is_recovery=is_recovery)
                    
        # Cascading deletes are done after parent locks are released
        # Handle Cascading Deletes
            
        # Log to undo stack
        if deleted_count > 0 and not is_recovery:
            self.undo_stack.append({"type": "DELETE", "table": table_name, "offsets": deleted_offsets})
            self.redo_stack.clear()
            
        return f"{deleted_count} row(s) deleted."

    def _execute_update(self, query, is_recovery=False):
        table_name = query["table"]
        set_col = query["set_col"]
        set_val = query["set_val"]
        conditions = query.get("conditions", [])

        if table_name not in self.tables:
            return f"Error: Table '{table_name}' does not exist."

        storage = self.tables[table_name]
        schema = self.schemas[table_name]
        
        set_col_idx = self._get_col_idx(schema, set_col)
        if set_col_idx == -1:
            return f"Error: Column '{set_col}' does not exist."

        # Query Optimizer: Pick the best index
        idx_cond = None
        best_b_tree = None
        for cond in conditions:
            if cond["op"] == "=" and cond["col"] in self.indexes.get(table_name, {}):
                idx_cond = cond
                best_b_tree = self.indexes[table_name][cond["col"]]
                break

        if query.get("explain"):
            plan = f"EXPLAIN PLAN FOR UPDATE on '{table_name}'\n"
            if idx_cond:
                plan += f"-> Strategy: Index Condition Pushdown (B-Tree on '{idx_cond['col']}')\n"
                plan += f"-> Step 1: O(log N) Index Scan on '{idx_cond['col']}' for value '{idx_cond['val']}'\n"
            else:
                plan += f"-> Strategy: Full Table Scan\n"
                plan += f"-> Step 1: O(N) Sequential read on '{table_name}'\n"
            plan += f"-> Step 2: O(1) In-place byte replacement\n"
            plan += f"-> Step 3: Write to Undo Log"
            return plan

        updated_count = 0
        targets = []
        targets_offsets = []
        
        # Subqueries and NOW() for UPDATE
        for cond in conditions:
            if cond["op"] == "IN" and "subquery" in cond:
                sub_parsed = self.parser.parse(cond["subquery"])
                sub_results = self.execute(sub_parsed)
                cond["val"] = [r[0] for r in sub_results]
            elif isinstance(cond["val"], str) and cond["val"].upper() == 'NOW()':
                from datetime import datetime
                cond["val"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if idx_cond:
            offset = best_b_tree.search(idx_cond["val"])
            if offset is not None:
                rec = storage.read_record(offset)
                if rec and self._evaluate_conditions(rec, schema, conditions):
                    targets.append(rec)
                    targets_offsets.append(offset)
        else:
            records, offsets = storage.read_all()
            for rec, offset in zip(records, offsets):
                if self._evaluate_conditions(rec, schema, conditions):
                    targets.append(rec)
                    targets_offsets.append(offset)

        # Perform in-place updates and capture for undo
        old_records_data = []
        new_records_data = []
        for offset, rec in zip(targets_offsets, targets):
            self._acquire_row_lock(table_name, offset)
            try:
                new_rec = list(rec)
                new_rec[set_col_idx] = query["set_val"]
                new_rec = tuple(new_rec)
                
                self._run_triggers(table_name, "UPDATE", "BEFORE", old_rec=rec, new_rec=new_rec, schema=schema)
                
                old_records_data.append((offset, list(rec)))
                storage.update_record(offset, new_rec)
                new_records_data.append((offset, new_rec))
                
                self._run_triggers(table_name, "UPDATE", "AFTER", old_rec=rec, new_rec=new_rec, schema=schema)
                updated_count += 1
            finally:
                self._release_row_lock(table_name, offset)

        if updated_count > 0 and not is_recovery:
            self.undo_stack.append({
                "type": "UPDATE", 
                "table": table_name, 
                "old_records": old_records_data,
                "new_records": new_records_data
            })
            self.redo_stack.clear()

        return f"{updated_count} row(s) updated."

    def _get_col_idx(self, schema, col_name):
        for i, (name, dtype) in enumerate(schema):
            if name == col_name:
                return i
        return -1
