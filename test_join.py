from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE users (id INT, name STR)",
    "CREATE TABLE orders (order_id INT, user_id INT, amount FLOAT)",
    "INSERT INTO users VALUES (1, 'Alice')",
    "INSERT INTO users VALUES (2, 'Bob')",
    "INSERT INTO orders VALUES (101, 1, 99.5)",
    "INSERT INTO orders VALUES (102, 1, 45.0)",
    "INSERT INTO orders VALUES (103, 2, 20.0)",
    "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
]

for q in queries:
    print("QUERY:", q)
    print("RESULT:", db.execute(parser.parse(q)))
    print()
