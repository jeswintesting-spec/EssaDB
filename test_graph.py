from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    # Setup
    "CREATE TABLE users (id INT, name STR)",
    "INSERT INTO users VALUES (1, 'Alice')",
    "INSERT INTO users VALUES (2, 'Bob')",
    "INSERT INTO users VALUES (3, 'Charlie')",
    
    # 1. Edges
    "CREATE EDGE follows FROM users(1) TO users(2)",
    "CREATE EDGE follows FROM users(1) TO users(3)",
    "CREATE EDGE likes FROM users(2) TO users(3)",
    
    # 2. MATCH Traversals
    "MATCH (users) -[follows]-> (users) WHERE id = 1",
    "MATCH (users) -[likes]-> (users) WHERE id = 2"
]

for q in queries:
    print("QUERY:", q)
    try:
        res = db.execute(parser.parse(q))
        print("RESULT:\n" + str(res))
    except Exception as e:
        print("EXCEPTION:", str(e))
    print("-" * 50)
