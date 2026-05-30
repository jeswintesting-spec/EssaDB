from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE students (id INT, age INT, name STR)",
    "CREATE INDEX idx_age ON students(age)",
    "EXPLAIN INSERT INTO students VALUES (1, 20, 'Alice')",
    "INSERT INTO students VALUES (1, 20, 'Alice')",
    "INSERT INTO students VALUES (2, 22, 'Bob')",
    "INSERT INTO students VALUES (3, 22, 'Charlie')",
    "EXPLAIN SELECT * FROM students WHERE id = 1",
    "EXPLAIN SELECT * FROM students WHERE age = 22",
    "EXPLAIN SELECT * FROM students WHERE name = 'Bob'",
    "SELECT * FROM students WHERE age = 22",
]

for q in queries:
    print("QUERY:", q)
    print("RESULT:\n" + str(db.execute(parser.parse(q))))
    print("-" * 50)
