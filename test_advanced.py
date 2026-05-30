from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    # 1. Foreign Keys and Cascading Deletes
    "CREATE TABLE users (id INT, name STR)",
    "CREATE TABLE orders (id INT, amount FLOAT, user_id INT REFERENCES users(id) ON DELETE CASCADE)",
    "INSERT INTO users VALUES (1, 'Alice')",
    "INSERT INTO users VALUES (2, 'Bob')",
    "INSERT INTO orders VALUES (101, 50.5, 1)",
    "INSERT INTO orders VALUES (102, 100.0, 1)",
    "INSERT INTO orders VALUES (103, 75.0, 2)",
    "INSERT INTO orders VALUES (104, 500.0, 99)", # Should fail!
    
    "SELECT * FROM orders",
    "DELETE FROM users WHERE id = 1", # Should cascade and delete Alice's orders
    "SELECT * FROM orders",
    
    # 2. ORDER BY and LIMIT
    "CREATE TABLE leaderboard (id INT, score FLOAT)",
    "INSERT INTO leaderboard VALUES (1, 100.0)",
    "INSERT INTO leaderboard VALUES (2, 500.0)",
    "INSERT INTO leaderboard VALUES (3, 250.0)",
    "INSERT INTO leaderboard VALUES (4, 900.0)",
    "SELECT * FROM leaderboard ORDER BY score DESC LIMIT 2",
]

for q in queries:
    print("QUERY:", q)
    try:
        res = db.execute(parser.parse(q))
        print("RESULT:\n" + str(res))
    except Exception as e:
        print("EXCEPTION:", str(e))
    print("-" * 50)
