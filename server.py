import socket
import threading
import json
import struct
from engine import DatabaseEngine
from parser import QueryParser

HOST = '127.0.0.1'
PORT = 9999

class DatabaseServer:
    def __init__(self, db_dir):
        self.db = DatabaseEngine(db_dir)
        self.parser = QueryParser()
        self.general_lock = threading.Lock()
        self.tx_lock = threading.Lock()
        self.tx_owner = None
        
    def _send_msg(self, conn, msg_dict):
        data = json.dumps(msg_dict).encode('utf-8')
        conn.sendall(struct.pack('!I', len(data)) + data)
        
    def _recv_msg(self, conn):
        raw_msglen = self._recvall(conn, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('!I', raw_msglen)[0]
        data = self._recvall(conn, msglen)
        return json.loads(data.decode('utf-8'))
        
    def _recvall(self, conn, n):
        data = bytearray()
        while len(data) < n:
            packet = conn.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def handle_client(self, conn, addr):
        print(f"[NEW CONNECTION] {addr} connected.")
        client_id = threading.get_ident()
        try:
            while True:
                req = self._recv_msg(conn)
                if not req:
                    break
                    
                query_str = req.get("query")
                if not query_str:
                    continue
                    
                try:
                    parsed = self.parser.parse(query_str)
                    
                    if parsed["type"] == "BEGIN":
                        if self.tx_owner is not None and self.tx_owner != client_id:
                            self._send_msg(conn, {"status": "error", "message": "Database is locked by another transaction."})
                            continue
                        if self.tx_owner == client_id:
                            self._send_msg(conn, {"status": "error", "message": "You are already in a transaction."})
                            continue
                        
                        self.tx_lock.acquire()
                        self.tx_owner = client_id
                        result = self.db.execute(parsed)
                        self._send_msg(conn, {"status": "success", "result": result, "schema": None})
                        continue

                    if self.tx_owner is not None and self.tx_owner != client_id:
                        self._send_msg(conn, {"status": "error", "message": "Database is locked by another transaction. Please try again later."})
                        continue

                    if parsed["type"] in ("COMMIT", "ROLLBACK"):
                        if self.tx_owner != client_id:
                            self._send_msg(conn, {"status": "error", "message": "No active transaction."})
                            continue
                            
                        result = self.db.execute(parsed)
                        self.tx_owner = None
                        self.tx_lock.release()
                        self._send_msg(conn, {"status": "success", "result": result, "schema": None})
                        continue

                    # Normal queries execution
                    if self.tx_owner == client_id:
                        result = self.db.execute(parsed)
                    else:
                        with self.general_lock:
                            result = self.db.execute(parsed)
                            
                    schema = None
                    if parsed.get("explain"):
                        pass
                    elif parsed["type"] == "SELECT":
                        t1_name = parsed["table"]
                        t1_schema = self.db.schemas.get(t1_name, [])
                        
                        if parsed.get("join_table"):
                            t2_name = parsed["join_table"]
                            t2_schema = self.db.schemas.get(t2_name, [])
                            base_schema = [(f"{t1_name}.{c}", t) for c, t in t1_schema] + \
                                          [(f"{t2_name}.{c}", t) for c, t in t2_schema]
                        else:
                            base_schema = t1_schema
                            
                        targets = parsed.get("targets", [{"type": "ALL"}])
                        if len(targets) == 1 and targets[0]["type"] == "ALL":
                            schema = base_schema
                        else:
                            col_type_map = {name: dtype for name, dtype in base_schema}
                            schema = []
                            for target in targets:
                                if target["type"] == "COL":
                                    schema.append((target["col"], col_type_map.get(target["col"], "STR")))
                                elif target["type"] == "AGG":
                                    func = target["func"]
                                    col = target["col"]
                                    label = f"{func}({col})"
                                    if func == "COUNT":
                                        schema.append((label, "INT"))
                                    else:
                                        schema.append((label, "FLOAT"))
                                        
                    elif parsed["type"] == "SHOW_TABLES":
                        schema = [("Table Name", "STR")]
                    elif parsed["type"] == "DESCRIBE":
                        schema = [("Column Name", "STR"), ("Data Type", "STR")]
                        
                    self._send_msg(conn, {"status": "success", "result": result, "schema": schema})
                except Exception as e:
                    self._send_msg(conn, {"status": "error", "message": str(e)})
                    
        except ConnectionResetError:
            pass
        finally:
            if self.tx_owner == client_id:
                self.db.execute({"type": "ROLLBACK"})
                self.tx_owner = None
                self.tx_lock.release()
            print(f"[DISCONNECTED] {addr} disconnected.")
            conn.close()

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f"[STARTING] EssaDB Server daemon is listening on {HOST}:{PORT}...")
        
        try:
            while True:
                conn, addr = server.accept()
                thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                thread.start()
                print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Server is shutting down.")
            server.close()

if __name__ == "__main__":
    print("Booting EssaDB Engine...")
    server = DatabaseServer("./data")
    server.start()
