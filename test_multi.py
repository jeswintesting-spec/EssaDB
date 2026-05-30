from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")
db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE users (id INT, name STR)",
    "INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Charlie')",
    "SELECT * FROM users"
]

for q in queries:
    print("Executing:", q)
    print(db.execute(parser.parse(q)))
