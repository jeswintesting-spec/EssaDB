from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE events (id INT, payload JSON)",
    "INSERT INTO events VALUES (1, {\"status\": \"error\", \"code\": 500})",
    "INSERT INTO events VALUES (2, {\"status\": \"success\", \"user\": \"jeswin\"})",
    "INSERT INTO events VALUES (3, {\"status\": \"error\", \"code\": 404})",
    "SELECT * FROM events",
    "SELECT * FROM events WHERE payload->>'status' = 'error'",
    "SELECT * FROM events WHERE payload->>'code' = 500",
]

for q in queries:
    print("QUERY:", q)
    try:
        res = db.execute(parser.parse(q))
        print("RESULT:\n" + str(res))
    except Exception as e:
        print("EXCEPTION:", str(e))
    print("-" * 50)
