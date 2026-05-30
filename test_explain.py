from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE users (id INT, name STR)",
    "EXPLAIN INSERT INTO users VALUES (1, 'Alice')",
    "INSERT INTO users VALUES (1, 'Alice')",
    "EXPLAIN SELECT * FROM users WHERE id = 1 AND name = 'Alice'",
    "EXPLAIN SELECT * FROM users WHERE name = 'Alice'",
    "EXPLAIN UPDATE users SET name = 'Bob' WHERE id = 1",
    "EXPLAIN DELETE FROM users WHERE name = 'Bob'",
]

for q in queries:
    print("QUERY:", q)
    print("RESULT:\n" + str(db.execute(parser.parse(q))))
    print("-" * 50)
