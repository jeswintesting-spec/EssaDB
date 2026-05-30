from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE logs (id INT, message STR, created_at DATETIME)",
    "INSERT INTO logs VALUES (1, 'System Boot', '2020-01-01 10:00:00')",
    "INSERT INTO logs VALUES (2, 'User Login', NOW())",
    "SELECT * FROM logs",
    "SELECT * FROM logs WHERE created_at < NOW()"
]

for q in queries:
    print("QUERY:", q)
    try:
        res = db.execute(parser.parse(q))
        print("RESULT:\n" + str(res))
    except Exception as e:
        print("EXCEPTION:", str(e))
    print("-" * 50)
