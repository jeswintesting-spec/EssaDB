import socket
import json
import struct

class EssaDBClient:
    def __init__(self, host='127.0.0.1', port=9999):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        
    def _send_msg(self, msg_dict):
        data = json.dumps(msg_dict).encode('utf-8')
        self.sock.sendall(struct.pack('!I', len(data)) + data)
        
    def _recv_msg(self):
        raw_msglen = self._recvall(4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('!I', raw_msglen)[0]
        data = self._recvall(msglen)
        return json.loads(data.decode('utf-8'))
        
    def _recvall(self, n):
        data = bytearray()
        while len(data) < n:
            packet = self.sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def execute(self, query):
        """Execute a SQL query against EssaDB."""
        self._send_msg({"query": query})
        response = self._recv_msg()
        if response.get("status") == "success":
            return response.get("result")
        else:
            raise Exception(f"EssaDB Error: {response.get('error', response.get('message'))}")
            
    def close(self):
        self.sock.close()

# --- EXAMPLE USAGE IN A WEB APP ---
if __name__ == "__main__":
    db = EssaDBClient()
    
    # 1. Setup table
    try:
        db.execute("CREATE TABLE web_users (id INT, username STR, email STR)")
    except: pass # Ignore if already exists
    
    # 2. Insert data (Like a user signing up on a website)
    db.execute("INSERT INTO web_users VALUES (1, 'jeswin', 'jeswin@example.com')")
    db.execute("INSERT INTO web_users VALUES (2, 'astra', 'astra@example.com')")
    
    # 3. Fetch data (Like logging a user in)
    users = db.execute("SELECT * FROM web_users WHERE username = 'jeswin'")
    
    print("Fetched User Profile:")
    print(users)
    
    db.close()
