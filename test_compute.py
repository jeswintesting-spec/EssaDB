from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    # Setup
    "CREATE TABLE stats (id INT, name STR, score FLOAT)",
    
    # Insert Data
    "INSERT INTO stats VALUES (1, 'Alice', -45.67)",
    "INSERT INTO stats VALUES (2, 'Bob', 12.34)",
    
    # Test Functions
    "SELECT UPPER(name), ABS(score), ROUND(score), LENGTH(name) FROM stats"
]

for q in queries:
    print("QUERY:", q)
    try:
        res = db.execute(parser.parse(q))
        print("RESULT:\n" + str(res))
    except Exception as e:
        print("EXCEPTION:", str(e))
    print("-" * 50)
