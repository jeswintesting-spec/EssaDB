# EssaDB

![EssaDB Banner](https://img.shields.io/badge/Architecture-Custom_RDBMS-blue)
![Language](https://img.shields.io/badge/Language-Pure_Python-green)
![Status](https://img.shields.io/badge/Status-Production_Ready-brightgreen)

**EssaDB** is a high-performance, multi-model database engine built entirely from scratch in pure Python. 

Rather than wrapping an existing engine like SQLite, EssaDB implements every major Computer Science subsystem required for a production database: from low-level C-style binary byte packing (`struct`), to disk-based $O(\log N)$ B-Tree indexing, up to a custom SQL parser capable of executing advanced AI Vector searches and Graph traversals.

## 🚀 Architectural Masterpieces

EssaDB is built with the following advanced subsystems:

1. **Custom Binary Storage System**: Tables are dynamically compiled into fixed-length binary records using Python's `struct`, ensuring $O(1)$ random-access disk seeks without needing to load the whole file into RAM.
2. **B-Tree Indexing & Pager Engine**: A fully functional B-Tree implementation with an LRU (Least Recently Used) Buffer Pool Cache for ultra-fast lookups.
3. **Write-Ahead Logging (WAL)**: Ensures 100% ACID compliance and data durability. Transactions are logged as byte streams and can be recovered if the server crashes.
4. **Multi-Version Concurrency Control (MVCC)**: Implements micro-row-level locking and thread-safe file pointer I/O, allowing thousands of concurrent `SELECT` readers without being blocked by `UPDATE` writers.
5. **Multi-Model Engine**: Seamlessly parses and executes standard Relational SQL, NoSQL JSON document queries, Cypher-style Graph Network traversals, and AI Vector Cosine-Similarity searches within a single runtime.
6. **Time-Series Compute Layer**: Features native window functions (`RUNNING_TOTAL`, `LAG`) and scalar compute functions (`UPPER`, `LENGTH`, `ROUND`).
7. **Event-Driven Subsystem**: Native support for `BEFORE`/`AFTER` Triggers and dynamic Virtual Views.

## 📦 Getting Started

### 1. Booting the Server
EssaDB operates as a headless daemon listening on a TCP socket, fully supporting multi-threaded concurrent client requests.

```bash
# Start the database server on 127.0.0.1:9999
python main.py
```

### 2. Using the GUI Visualizer
EssaDB comes with a built-in `tkinter` Graphical User Interface (GUI) to view schemas, execute SQL queries, and export results directly to CSV.

```bash
# Open the Visualizer UI
python visualizer.py
```

### 3. Integrating with your Web Apps
You can use EssaDB to power your Flask, Django, or FastAPI backends! Simply drop `essadb_driver.py` into your project.

```python
from essadb_driver import EssaDBClient

db = EssaDBClient()
users = db.execute("SELECT * FROM users WHERE status = 'active'")
db.close()
```

## 📖 Documentation
For a complete and highly detailed breakdown of all supported SQL queries, NoSQL functions, Graph syntax, and AI commands, please read the [**USER_MANUAL.md**](./USER_MANUAL.md).

## 🛠 Project Structure
- `engine.py` - The core query execution, lock management, and optimizer.
- `parser.py` - Custom regex-based AST compiler mapping strings to operations.
- `storage.py` - The byte-packing layer, translating Python objects to binary.
- `btree.py` - Disk-backed hierarchical index tree with LRU caching.
- `wal.py` - The crash-recovery transaction logger.
- `server.py` - Multi-threaded TCP network handler.
- `visualizer.py` - The standalone interactive GUI client.
- `essadb_driver.py` - Drop-in driver for external Python applications.
