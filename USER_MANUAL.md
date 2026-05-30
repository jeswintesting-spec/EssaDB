# EssaDB User Manual

This manual provides a comprehensive breakdown of the EssaDB Query Language, a custom hybrid SQL dialect that natively supports Relational Data, Graph Networks, JSON Documents, and AI Vectors.

---

## 1. Data Definition & Architecture

### Creating Tables
You can create tables with typed columns. Supported types include `INT`, `FLOAT`, `STR`, `BOOL`, `JSON`, `DATETIME`, and `VECTOR`.
```sql
CREATE TABLE users (id INT, name STR, age INT, profile JSON, created_at DATETIME)
```

### Creating B-Tree Indices
To speed up `$O(N)$` full-table scans to `$O(\log N)$` index lookups, create an index on frequently searched columns.
```sql
CREATE INDEX idx_user_id ON users (id)
```

### Relational Foreign Keys
Ensure referential integrity across tables. Cascading deletes are fully supported.
```sql
CREATE TABLE orders (id INT, user_id INT, amount FLOAT)
FOREIGN KEY orders(user_id) REFERENCES users(id) ON DELETE CASCADE
```

---

## 2. Basic Data Manipulation (DML)

### Inserting Data
The `DATETIME` type natively supports a `NOW()` evaluation macro that resolves to the system clock on the server.
```sql
INSERT INTO users VALUES (1, 'Alice', 28, {"theme": "dark"}, NOW())
```

### Updating Data
Modify existing data efficiently. Row-level locks (MVCC) ensure thread safety.
```sql
UPDATE users SET age = 29 WHERE id = 1
```

### Deleting Data
Rows are marked with a Tombstone byte in the binary `dat` file, executing instantly.
```sql
DELETE FROM users WHERE name = 'Alice'
```

---

## 3. Advanced Querying

### Standard Filtering & Joins
Filter data using `=`, `!=`, `>`, `<`, `>=`, `<=`, and perform nested relational Subqueries.
```sql
SELECT name, age FROM users WHERE id IN (SELECT user_id FROM orders)
```
```sql
SELECT * FROM users JOIN orders ON users.id = orders.user_id
```

### Aggregations & Grouping
Compute large-scale metrics.
```sql
SELECT COUNT(id), AVG(age), SUM(amount) FROM users GROUP BY age
```

---

## 4. Compute Layer & Time-Series Analytics

### Scalar Functions
Dynamically transform data during the selection phase using Python's native string and math algorithms.
*   **Strings**: `UPPER(col)`, `LOWER(col)`, `LENGTH(col)`
*   **Math**: `ABS(col)`, `ROUND(col)`
```sql
SELECT UPPER(name), LENGTH(name) FROM users
```

### Time-Series Window Functions
Perform memory calculations sequentially across rows in the dataset.
*   `RUNNING_TOTAL(col)`: Computes a cumulative running sum.
*   `LAG(col)`: Returns the value of the previous row.
*   `CUMULATIVE_AVG(col)`: Returns a moving average.
```sql
SELECT id, amount, RUNNING_TOTAL(amount) FROM orders ORDER BY id ASC
```

---

## 5. Automation & Abstraction

### Triggers (Event Hooks)
Automate logic based on `BEFORE` or `AFTER` events for `INSERT`, `UPDATE`, or `DELETE`.
```sql
CREATE TRIGGER log_delete AFTER DELETE ON users BEGIN INSERT INTO log VALUES (99, 'User Deleted') END
```

### Virtual Views
Save complex multi-join or aggregated queries as dynamic tables.
```sql
CREATE VIEW active_users AS SELECT * FROM users WHERE status = 'active'
-- Then query it like a normal table:
SELECT * FROM active_users
```

---

## 6. Multi-Model Paradigm

### NoSQL JSON Documents
EssaDB natively integrates NoSQL key lookups into SQL syntax using the `->>` operator.
```sql
-- Select all users who have the dark theme applied inside their JSON config
SELECT * FROM users WHERE profile->>theme = 'dark'
```

### AI Vector Engine
Perform cosine similarity searches natively inside the database. This is identical to the functionality of Pinecone or ChromaDB.
```sql
CREATE TABLE embeddings (id INT, data VECTOR)
INSERT INTO embeddings VALUES (1, [0.1, 0.9, 0.2])

-- Order the results by mathematical similarity to the target vector
SELECT * FROM embeddings ORDER BY SIMILARITY(data, [0.1, 1.0, 0.0]) DESC LIMIT 5
```

### Graph Database Subsystem
Treat tables as nodes and draw relational edges between them. Use Cypher syntax to traverse the network.
```sql
-- 1. Create a bidirectional edge between User 1 and User 2
CREATE EDGE 'FRIENDS' FROM users(1) TO users(2)

-- 2. Traverse the graph! Find everyone who is friends with User 1
MATCH (users WHERE id = 1)-[:FRIENDS]->(users)
```

---

## 7. ACID Transactions
Wrap multiple operations in a transaction block. If an error occurs, the Write-Ahead Log (WAL) can revert all changes via the Undo stack.
```sql
BEGIN
INSERT INTO orders VALUES (10, 1, 500)
UPDATE users SET balance = 0 WHERE id = 1
COMMIT
```
If something goes wrong:
```sql
ROLLBACK
```
