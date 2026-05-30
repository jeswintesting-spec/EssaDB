from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    # Setup
    "CREATE TABLE users (id INT, name STR, status STR)",
    "CREATE TABLE log (id INT, message STR)",
    "INSERT INTO users VALUES (1, 'Alice', 'active')",
    "INSERT INTO users VALUES (2, 'Bob', 'inactive')",
    "INSERT INTO users VALUES (3, 'Charlie', 'active')",
    
    # 1. Triggers
    "CREATE TRIGGER log_del AFTER DELETE ON users BEGIN INSERT INTO log VALUES (99, 'User Deleted') END",
    "DELETE FROM users WHERE id = 2",
    "SELECT * FROM log",
    
    # 2. Virtual Views
    "CREATE VIEW active_users AS SELECT id, name FROM users WHERE status = 'active'",
    "SELECT * FROM active_users",
    
    # 3. Subqueries
    "CREATE TABLE orders (id INT, user_id INT, amount FLOAT)",
    "INSERT INTO orders VALUES (101, 1, 50.0)",
    "INSERT INTO orders VALUES (102, 3, 100.0)",
    "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)",
]

for q in queries:
    print("QUERY:", q)
    try:
        res = db.execute(parser.parse(q))
        print("RESULT:\n" + str(res))
    except Exception as e:
        print("EXCEPTION:", str(e))
    print("-" * 50)
