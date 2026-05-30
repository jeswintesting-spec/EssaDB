import socket
import json
import struct
import time
import readline
import os
import atexit
from rich.console import Console
from rich.table import Table

# Setup Readline History
histfile = os.path.join(os.path.expanduser("~"), ".essadb_history")
try:
    readline.read_history_file(histfile)
    readline.set_history_length(1000)
except FileNotFoundError:
    pass
atexit.register(readline.write_history_file, histfile)

# Setup SQL Auto-completion
def sql_completer(text, state):
    keywords = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'TABLE', 'INDEX', 
        'FROM', 'WHERE', 'VALUES', 'SET', 'BEGIN', 'COMMIT', 'ROLLBACK', 
        'VACUUM', 'EXPLAIN', 'JOIN', 'ON', 'GROUP BY', 'ORDER BY', 'LIMIT', 
        'ASC', 'DESC', 'SHOW TABLES', 'DESCRIBE'
    ]
    options = [k for k in keywords if k.startswith(text.upper())]
    if state < len(options):
        return options[state]
    return None

readline.set_completer(sql_completer)
readline.parse_and_bind("tab: complete")

HOST = '127.0.0.1'
PORT = 9999
console = Console()

def send_msg(conn, msg_dict):
    data = json.dumps(msg_dict).encode('utf-8')
    conn.sendall(struct.pack('!I', len(data)) + data)
    
def recv_msg(conn):
    raw_msglen = recvall(conn, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('!I', raw_msglen)[0]
    data = recvall(conn, msglen)
    return json.loads(data.decode('utf-8'))
    
def recvall(conn, n):
    data = bytearray()
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

def print_results(results, schema, query_time):
    if not results and schema is not None:
        console.print(f"No results. ({query_time:.4f}s)", style="yellow")
        return
    
    if schema is None:
        if isinstance(results, str):
            console.print(results, style="green")
        return

    table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    for col_name, _ in schema:
        table.add_column(col_name)
    
    for row in results:
        table.add_row(*[str(x) for x in row])
    
    console.print(table)
    console.print(f"{len(results)} row(s) returned in {query_time:.4f}s.", style="dim")

def main():
    console.print(r"""[bold cyan]
    ______                ____  ____ 
   / ____/_____________ _/ __ \/ __ )
  / __/ / ___/ ___/ __ `/ / / / __  |
 / /___(__  |__  ) /_/ / /_/ / /_/ / 
/_____/____/____/\__,_/_____/_____/ 
    [/bold cyan]""")
    console.print("[bold green]EssaDB - Client Interface[/bold green]")
    console.print("Type 'exit' to quit. Use SQL-like syntax (e.g. CREATE TABLE, INSERT INTO, SELECT).")
    print("-" * 50)
    
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((HOST, PORT))
        console.print(f"Connected to EssaDB server at {HOST}:{PORT}", style="green")
    except ConnectionRefusedError:
        console.print("[bold red]Connection failed![/bold red] Make sure the server daemon is running.", style="red")
        return
        
    while True:
        try:
            # Get multi-line input
            query = console.input("[bold yellow]EssaDB > [/bold yellow]")
            if query.lower() in ("exit", "quit", ".exit"):
                console.print("Goodbye!", style="cyan")
                break
            if not query.strip():
                continue
            
            start_time = time.time()
            send_msg(client, {"query": query})
            response = recv_msg(client)
            end_time = time.time()
            
            if not response:
                console.print("[red bold]Server closed the connection.[/red bold]")
                break
                
            if response["status"] == "error":
                console.print(f"Error: {response['message']}", style="red bold")
            else:
                print_results(response["result"], response.get("schema"), end_time - start_time)
                
        except Exception as e:
            console.print(f"Connection Error: {e}", style="red bold")
            break
            
    client.close()

if __name__ == "__main__":
    main()
