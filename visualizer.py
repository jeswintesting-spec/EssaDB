import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import socket
import json
import csv
import os

HOST = '127.0.0.1'
PORT = 9999

class EssaDBVisualizer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EssaDB Visualizer & Data Exporter")
        self.geometry("900x600")
        self.configure(bg="#1e1e1e")
        self.current_data = []
        self.current_columns = []
        
        self._build_ui()
        
    def _build_ui(self):
        # Top Panel: Schema and Query
        top_frame = tk.Frame(self, bg="#1e1e1e")
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Schema Sidebar (Reads local essadb.meta if available)
        schema_frame = tk.LabelFrame(top_frame, text="Local Schema", bg="#252526", fg="white", font=("Arial", 10, "bold"))
        schema_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        self.schema_list = tk.Listbox(schema_frame, bg="#1e1e1e", fg="#4EC9B0", font=("Consolas", 10), height=8, width=25)
        self.schema_list.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.schema_list.bind("<Double-Button-1>", self._insert_table_name)
        self._load_local_schema()
        
        # Query Editor
        query_frame = tk.Frame(top_frame, bg="#1e1e1e")
        query_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(query_frame, text="SQL Query:", bg="#1e1e1e", fg="white", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.query_text = tk.Text(query_frame, height=6, bg="#1e1e1e", fg="#CE9178", font=("Consolas", 12), insertbackground="white")
        self.query_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.query_text.insert("1.0", "SELECT * FROM sales")
        
        # Buttons
        btn_frame = tk.Frame(query_frame, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X)
        
        tk.Button(btn_frame, text="Execute Query", bg="#007ACC", fg="white", font=("Arial", 10, "bold"), command=self.execute_query).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Export CSV", bg="#28A745", fg="white", font=("Arial", 10, "bold"), command=self.export_csv).pack(side=tk.RIGHT, padx=5)
        
        # Results Grid (Treeview)
        grid_frame = tk.Frame(self, bg="#1e1e1e")
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Style the Treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#252526", foreground="#D4D4D4", rowheight=25, fieldbackground="#252526")
        style.configure("Treeview.Heading", background="#333333", foreground="white", font=("Arial", 10, "bold"))
        style.map("Treeview", background=[("selected", "#094771")])
        
        # Scrollbars
        y_scroll = ttk.Scrollbar(grid_frame)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tree = ttk.Treeview(grid_frame, yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.tree.yview)
        x_scroll.config(command=self.tree.xview)

    def _load_local_schema(self):
        meta_path = "./data/essadb.meta"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    for table_name, schema in meta.get("schemas", {}).items():
                        if not table_name.startswith("_"):
                            cols = ", ".join([col[0] for col in schema])
                            self.schema_list.insert(tk.END, f"{table_name}")
            except:
                pass
                
    def _insert_table_name(self, event):
        selection = self.schema_list.curselection()
        if selection:
            table_name = self.schema_list.get(selection[0])
            self.query_text.delete("1.0", tk.END)
            self.query_text.insert("1.0", f"SELECT * FROM {table_name}")

    def _send_msg(self, sock, msg_dict):
        import struct
        data = json.dumps(msg_dict).encode('utf-8')
        sock.sendall(struct.pack('!I', len(data)) + data)
        
    def _recv_msg(self, sock):
        import struct
        raw_msglen = self._recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('!I', raw_msglen)[0]
        data = self._recvall(sock, msglen)
        return json.loads(data.decode('utf-8'))
        
    def _recvall(self, sock, n):
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def execute_query(self):
        query = self.query_text.get("1.0", tk.END).strip()
        if not query:
            return
            
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                self._send_msg(s, {"query": query})
                response = self._recv_msg(s)
                    
            if response and response.get("status") == "success":
                self.populate_grid(query, response.get("result"))
            else:
                messagebox.showerror("Query Error", str(response.get("error", response.get("message", "Unknown error"))))
                
        except ConnectionRefusedError:
            messagebox.showerror("Connection Error", "Could not connect to EssaDB Server. Is 'python main.py' running on port 9999?")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def populate_grid(self, query, result):
        # Clear existing
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = ()
        self.current_data = []
        self.current_columns = []
        
        if isinstance(result, str):
            # It's an action message (e.g. "1 row inserted")
            self.tree["columns"] = ("Result",)
            self.tree.heading("Result", text="Result")
            self.tree.insert("", tk.END, values=(result,))
            self.current_columns = ["Result"]
            self.current_data = [[result]]
            return
            
        if not result or not isinstance(result, list):
            self.tree["columns"] = ("Notice",)
            self.tree.heading("Notice", text="Notice")
            self.tree.insert("", tk.END, values=("Query executed successfully, but returned no rows.",))
            return
            
        # Dynamically infer columns from the width of the first row
        num_cols = len(result[0])
        self.current_columns = [f"Col {i+1}" for i in range(num_cols)]
        
        # Try to extract actual column names from the query if it's a SELECT
        upper_q = query.upper()
        if upper_q.startswith("SELECT") and "FROM" in upper_q:
            select_part = query[6:upper_q.find("FROM")].strip()
            if select_part != "*":
                cols = [c.strip() for c in select_part.split(",")]
                if len(cols) == num_cols:
                    self.current_columns = cols

        self.tree["columns"] = self.current_columns
        self.tree["show"] = "headings"
        
        for col in self.current_columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, anchor=tk.W)
            
        for row in result:
            self.tree.insert("", tk.END, values=tuple(row))
            self.current_data.append(list(row))
            
    def export_csv(self):
        if not self.current_data:
            messagebox.showwarning("No Data", "There is no data to export. Execute a query first.")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Export Data as CSV"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.current_columns)
                    writer.writerows(self.current_data)
                messagebox.showinfo("Success", f"Data exported successfully to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to write CSV: {str(e)}")

if __name__ == "__main__":
    app = EssaDBVisualizer()
    app.mainloop()
