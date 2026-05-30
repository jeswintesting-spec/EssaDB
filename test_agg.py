from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE orders (id INT, department STR, amount FLOAT)",
    "INSERT INTO orders VALUES (1, 'Sales', 100.5)",
    "INSERT INTO orders VALUES (2, 'Sales', 200.0)",
    "INSERT INTO orders VALUES (3, 'HR', 50.0)",
    "INSERT INTO orders VALUES (4, 'HR', 75.0)",
    "INSERT INTO orders VALUES (5, 'Engineering', 900.0)",
    "SELECT COUNT(id), SUM(amount) FROM orders",
    "SELECT department, COUNT(id), SUM(amount), AVG(amount) FROM orders GROUP BY department"
]

for q in queries:
    print("QUERY:", q)
    print("RESULT:\n" + str(db.execute(parser.parse(q))))
    print("-" * 50)
