import re

class QueryParser:
    """
    Parses AQL (Astra Query Language).
    Now supports CREATE, INSERT, SELECT, UPDATE, and DELETE.
    """
    def parse(self, query):
        query = query.strip()
        is_explain = False
        if query.upper().startswith("EXPLAIN "):
            is_explain = True
            query = query[8:].strip()
            
        parsed = None
        if query.upper().startswith("CREATE VIEW"):
            match = re.match(r"CREATE VIEW (\w+) AS (.+)", query, re.IGNORECASE)
            if not match: raise ValueError("Syntax error in CREATE VIEW")
            parsed = {
                "type": "CREATE_VIEW",
                "view_name": match.group(1),
                "select_query": match.group(2).strip()
            }
            if is_explain: parsed["explain"] = True
            return parsed
            
        if query.upper().startswith("CREATE TRIGGER"):
            match = re.match(r"CREATE TRIGGER (\w+) (AFTER|BEFORE) (INSERT|UPDATE|DELETE) ON (\w+) BEGIN (.+) END", query, re.IGNORECASE)
            if not match: raise ValueError("Syntax error in CREATE TRIGGER")
            parsed = {
                "type": "CREATE_TRIGGER",
                "trigger_name": match.group(1),
                "timing": match.group(2).upper(),
                "event": match.group(3).upper(),
                "table": match.group(4),
                "action": match.group(5).strip()
            }
            if is_explain: parsed["explain"] = True
            return parsed

        if query.upper().startswith("CREATE EDGE"):
            match = re.match(r"CREATE EDGE (\w+) FROM (\w+)\((\d+)\) TO (\w+)\((\d+)\)", query, re.IGNORECASE)
            if not match: raise ValueError("Syntax error in CREATE EDGE")
            parsed = {
                "type": "CREATE_EDGE",
                "edge_type": match.group(1),
                "source_table": match.group(2),
                "source_id": int(match.group(3)),
                "target_table": match.group(4),
                "target_id": int(match.group(5))
            }
            if is_explain: parsed["explain"] = True
            return parsed
            
        if query.upper().startswith("MATCH"):
            match = re.match(r"MATCH\s*\(\s*(\w+)\s*\)\s*-\[\s*(\w+)\s*\]->\s*\(\s*(\w+)\s*\)(?:\s+WHERE\s+(.+))?", query, re.IGNORECASE)
            if not match: raise ValueError("Syntax error in MATCH")
            parsed = {
                "type": "MATCH",
                "source_table": match.group(1),
                "edge_type": match.group(2),
                "target_table": match.group(3),
                "conditions": []
            }
            if match.group(4):
                parsed["conditions"] = self._parse_conditions(match.group(4))
            if is_explain: parsed["explain"] = True
            return parsed

        if query.upper().startswith("CREATE TABLE"):
            parsed = self._parse_create(query)
        elif query.upper().startswith("INSERT INTO"):
            parsed = self._parse_insert(query)
        elif query.upper().startswith("SELECT"):
            parsed = self._parse_select(query)
        elif query.upper().startswith("DELETE FROM"):
            parsed = self._parse_delete(query)
        elif query.upper().startswith("UPDATE"):
            parsed = self._parse_update(query)
        elif query.upper().startswith("SHOW TABLES"):
            parsed = {"type": "SHOW_TABLES"}
        elif query.upper().startswith("DESCRIBE"):
            match = re.match(r"DESCRIBE (\w+)", query, re.IGNORECASE)
            if not match:
                raise ValueError("Syntax error in DESCRIBE")
            parsed = {"type": "DESCRIBE", "table": match.group(1)}
        elif query.upper().startswith("UNDO"):
            parsed = {"type": "UNDO"}
        elif query.upper().startswith("REDO"):
            parsed = {"type": "REDO"}
        elif query.upper().startswith("BEGIN"):
            parsed = {"type": "BEGIN"}
        elif query.upper().startswith("COMMIT"):
            parsed = {"type": "COMMIT"}
        elif query.upper().startswith("ROLLBACK"):
            parsed = {"type": "ROLLBACK"}
        elif query.upper().startswith("CREATE INDEX"):
            match = re.match(r"CREATE INDEX (\w+) ON (\w+)\s*\(\s*(\w+)\s*\)", query, re.IGNORECASE)
            if not match:
                raise ValueError("Syntax error in CREATE INDEX")
            parsed = {
                "type": "CREATE_INDEX",
                "index_name": match.group(1),
                "table": match.group(2),
                "col": match.group(3)
            }
        elif query.upper().startswith("VACUUM"):
            match = re.match(r"VACUUM (\w+)", query, re.IGNORECASE)
            if not match:
                raise ValueError("Syntax error in VACUUM")
            parsed = {"type": "VACUUM", "table": match.group(1)}
        else:
            raise ValueError(f"Unsupported query type or syntax error: {query}")
            
        if parsed:
            parsed["explain"] = is_explain
        return parsed

    def _parse_val(self, val_str):
        if not val_str:
            return None
        if val_str.startswith("'") and val_str.endswith("'"):
            return val_str[1:-1]
            
        if val_str.startswith("{") and val_str.endswith("}"):
            import json
            try:
                # Need to convert single quotes to double quotes for JSON parsing if used
                clean_json = val_str.replace("'", '"')
                return json.loads(clean_json)
            except:
                pass
        elif val_str.startswith('"') and val_str.endswith('"'):
            return val_str[1:-1]
            
        if val_str.upper() == 'TRUE': return True
        if val_str.upper() == 'FALSE': return False
            
        try:
            if '.' in val_str:
                return float(val_str)
            return int(val_str)
        except ValueError:
            return val_str

    def _parse_create(self, query):
        match = re.match(r"CREATE TABLE (\w+)\s*\((.+)\)", query, re.IGNORECASE)
        if not match:
            raise ValueError("Syntax error in CREATE TABLE")
        cols_str = match.group(2)
        columns = []
        foreign_keys = []
        for col in cols_str.split(","):
            col = col.strip()
            fk_match = re.search(r"(\w+)\s+(\w+)\s+REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)(?:\s+ON\s+DELETE\s+CASCADE)?", col, re.IGNORECASE)
            if fk_match:
                col_name = fk_match.group(1)
                col_type = fk_match.group(2).upper()
                ref_table = fk_match.group(3)
                ref_col = fk_match.group(4)
                cascade = "ON DELETE CASCADE" in col.upper()
                columns.append((col_name, col_type))
                foreign_keys.append({"col": col_name, "ref_table": ref_table, "ref_col": ref_col, "cascade": cascade})
            else:
                parts = col.split()
                if len(parts) != 2:
                    raise ValueError(f"Invalid column definition: {col}")
                columns.append((parts[0], parts[1].upper()))
        return {"type": "CREATE", "table": match.group(1), "columns": columns, "foreign_keys": foreign_keys}

    def _parse_insert(self, query):
        match = re.match(r"INSERT INTO (\w+)\s+VALUES\s*(.+)", query, re.IGNORECASE)
        if not match:
            raise ValueError("Syntax error in INSERT")
        table_name = match.group(1)
        values_block = match.group(2).strip()
        
        raw_rows = []
        current_row_str = ""
        in_string = False
        paren_level = 0
        
        for char in values_block:
            if char == "'":
                in_string = not in_string
                current_row_str += char
            elif not in_string:
                if char == '(':
                    if paren_level > 0: current_row_str += char
                    paren_level += 1
                elif char == ')':
                    paren_level -= 1
                    if paren_level == 0:
                        raw_rows.append(current_row_str)
                        current_row_str = ""
                    else:
                        current_row_str += char
                elif paren_level > 0:
                    current_row_str += char
            else:
                current_row_str += char
                
        all_rows = []
        for row_str in raw_rows:
            values = []
            current = ""
            in_string = False
            bracket_level = 0
            brace_level = 0
            
            for char in row_str:
                if char == "'":
                    in_string = not in_string
                elif not in_string:
                    if char == '{': brace_level += 1
                    elif char == '}': brace_level -= 1
                    elif char == '[': bracket_level += 1
                    elif char == ']': bracket_level -= 1
                    elif char == ',' and brace_level == 0 and bracket_level == 0:
                        values.append(self._parse_val(current.strip()))
                        current = ""
                        continue
                current += char
                
            if current.strip():
                values.append(self._parse_val(current.strip()))
            all_rows.append(values)
            
        return {"type": "INSERT", "table": table_name, "rows": all_rows}

    def _parse_conditions(self, where_str):
        conditions = []
        parts = re.split(r'\s+AND\s+', where_str, flags=re.IGNORECASE)
        for part in parts:
            part = part.strip()
            
            # Subquery support: col IN (SELECT ...)
            match_in = re.search(r"([\w.\->>]+)\s+IN\s+\(\s*(SELECT.+)\s*\)", part, re.IGNORECASE)
            if match_in:
                col = match_in.group(1).strip()
                json_key = None
                if "->>" in col:
                    col, json_key = col.split("->>", 1)
                    col = col.strip()
                    json_key = json_key.strip().strip("'").strip('"')
                cond = {
                    "col": col,
                    "op": "IN",
                    "subquery": match_in.group(2).strip()
                }
                if json_key: cond["json_key"] = json_key
                conditions.append(cond)
                continue
                
            match = re.search(r"(?<!-|>)(>=|<=|!=|=|>|<)", part)
            if not match: continue
            
            op = match.group(1)
            col, val = part.split(op, 1)
            
            col = col.strip()
            json_key = None
            if "->>" in col:
                col, json_key = col.split("->>", 1)
                col = col.strip()
                json_key = json_key.strip().strip("'").strip('"')
                
            cond = {
                "col": col,
                "op": op,
                "val": self._parse_val(val.strip())
            }
            if json_key:
                cond["json_key"] = json_key
            conditions.append(cond)
        return conditions

    def _parse_targets(self, target_str):
        if target_str.strip() == "*":
            return [{"type": "ALL"}]
        
        targets = []
        parts = [p.strip() for p in target_str.split(",")]
        for part in parts:
            match_agg = re.match(r"(COUNT|SUM|AVG)\(([\w.]+)\)", part, re.IGNORECASE)
            match_func = re.match(r"(UPPER|LOWER|ROUND|LENGTH|ABS)\(([\w.]+)\)", part, re.IGNORECASE)
            match_win = re.match(r"(RUNNING_TOTAL|LAG|CUMULATIVE_AVG)\(([\w.]+)\)", part, re.IGNORECASE)
            
            if match_agg:
                targets.append({"type": "AGG", "func": match_agg.group(1).upper(), "col": match_agg.group(2)})
            elif match_func:
                targets.append({"type": "FUNC", "func": match_func.group(1).upper(), "col": match_func.group(2)})
            elif match_win:
                targets.append({"type": "WIN", "func": match_win.group(1).upper(), "col": match_win.group(2)})
            else:
                targets.append({"type": "COL", "col": part})
        return targets

    def _parse_select(self, query):
        base_match = re.match(r"SELECT\s+(.+?)\s+FROM\s+(\w+)(?:\s+JOIN\s+(\w+)\s+ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+))?(.*)$", query, re.IGNORECASE)
        if not base_match:
            raise ValueError("Syntax error in SELECT")
            
        targets_str = base_match.group(1)
        table = base_match.group(2)
        join_table = base_match.group(3)
        join_left_tbl = base_match.group(4)
        join_left_col = base_match.group(5)
        join_right_tbl = base_match.group(6)
        join_right_col = base_match.group(7)
        remainder = base_match.group(8).strip()
        
        group_by_str = None
        where_str = None
        order_by = None
        limit = None
        
        if remainder:
            limit_match = re.search(r"LIMIT\s+(\d+)$", remainder, re.IGNORECASE)
            if limit_match:
                limit = int(limit_match.group(1))
                remainder = remainder[:limit_match.start()].strip()
                
            order_match = re.search(r"ORDER BY\s+SIMILARITY\(([\w.]+),\s*(\[.*?\])\)(?:\s+(ASC|DESC))?$", remainder, re.IGNORECASE)
            if order_match:
                import json
                order_by = {
                    "type": "SIMILARITY",
                    "col": order_match.group(1),
                    "vector": json.loads(order_match.group(2)),
                    "dir": (order_match.group(3) or "DESC").upper()
                }
                remainder = remainder[:order_match.start()].strip()
            else:
                order_match = re.search(r"ORDER BY\s+([\w.]+)(?:\s+(ASC|DESC))?$", remainder, re.IGNORECASE)
                if order_match:
                    order_by = {
                        "type": "NORMAL",
                        "col": order_match.group(1),
                        "dir": (order_match.group(2) or "ASC").upper()
                    }
                    remainder = remainder[:order_match.start()].strip()

            group_match = re.search(r"GROUP BY\s+([\w.]+)$", remainder, re.IGNORECASE)
            if group_match:
                group_by_str = group_match.group(1)
                remainder = remainder[:group_match.start()].strip()
                
            if remainder.upper().startswith("WHERE "):
                where_str = remainder[6:].strip()
            elif remainder:
                raise ValueError(f"Syntax error near: {remainder}")
        
        conditions = []
        if where_str:
            conditions = self._parse_conditions(where_str)
            
        return {
            "type": "SELECT", 
            "targets": self._parse_targets(targets_str),
            "table": table,
            "join_table": join_table,
            "join_left_tbl": join_left_tbl,
            "join_left_col": join_left_col,
            "join_right_tbl": join_right_tbl,
            "join_right_col": join_right_col,
            "conditions": conditions,
            "group_by": group_by_str,
            "order_by": order_by,
            "limit": limit
        }

    def _parse_delete(self, query):
        match = re.match(r"DELETE FROM (\w+)", query, re.IGNORECASE)
        if not match:
            raise ValueError("Syntax error in DELETE")
            
        where_match = re.search(r"WHERE\s+(.+)$", query, re.IGNORECASE)
        conditions = []
        if where_match:
            conditions = self._parse_conditions(where_match.group(1))
            
        return {"type": "DELETE", "table": match.group(1), "conditions": conditions}

    def _parse_update(self, query):
        match = re.match(r"UPDATE (\w+) SET (\w+)\s*=\s*([^ ]+)", query, re.IGNORECASE)
        if not match:
            raise ValueError("Syntax error in UPDATE")
            
        where_match = re.search(r"WHERE\s+(.+)$", query, re.IGNORECASE)
        conditions = []
        if where_match:
            conditions = self._parse_conditions(where_match.group(1))
            
        return {
            "type": "UPDATE", 
            "table": match.group(1), 
            "set_col": match.group(2), 
            "set_val": self._parse_val(match.group(3)), 
            "conditions": conditions
        }
