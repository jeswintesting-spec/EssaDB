from engine import DatabaseEngine
from parser import QueryParser
import shutil
import os

if os.path.exists("./data"):
    shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE metrics (id INT, is_active BOOL, score FLOAT, name STR)",
    "SHOW TABLES",
    "DESCRIBE metrics",
    "INSERT INTO metrics VALUES (1, True, 99.5, 'Alice')",
    "INSERT INTO metrics VALUES (2, False, 85.0, 'Bob')",
    "INSERT INTO metrics VALUES (1, True, 100.0, 'Duplicate Alice')", # Should fail constraint
    "SELECT * FROM metrics",
]

for q in queries:
    print(f"QUERY: {q}")
    parsed = parser.parse(q)
    res = db.execute(parsed)
    print(f"RESULT: {res}\n")
