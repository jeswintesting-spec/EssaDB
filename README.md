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

## 📦 Getting Started (Step-by-Step for Beginners)

If you are new to programming, don't worry! Running EssaDB is incredibly simple. Just follow these steps:

### Step 1: Download the Project
First, clone this repository to your computer and navigate into the folder:
```bash
git clone https://github.com/jeswintesting-spec/EssaDB.git
cd EssaDB
```

### Step 2: Start the Database Server
EssaDB runs in the background (like a real database server) and listens for instructions on port `9999`. 
Open your terminal and type:
```bash
python server.py
```
*(Leave this terminal window open! This is your engine running in the background.)*

### Step 3: Open the Graphical Visualizer or CLI
Now that the server is running, you need a way to actually see and interact with your data. 
**Open a second, new terminal window** (keep the first one running), navigate to the `EssaDB` folder, and type:
```bash
python visualizer.py
```
*(Alternatively, you can type `python main.py` to use the text-based hacker terminal!)*
A beautiful dark-mode window will pop up! You can now type SQL queries, hit **Execute**, and see your data in a spreadsheet-style grid. You can even export it to CSV!

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
