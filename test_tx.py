from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE bank (id INT, balance FLOAT)",
    "INSERT INTO bank VALUES (1, 100.0)",
    "BEGIN",
    "UPDATE bank SET balance = 50.0 WHERE id = 1",
    "SELECT * FROM bank",
    "ROLLBACK",
    "SELECT * FROM bank",
    "BEGIN",
    "UPDATE bank SET balance = 1000.0 WHERE id = 1",
    "COMMIT",
    "SELECT * FROM bank"
]

for q in queries:
    print("QUERY:", q)
    print("RESULT:\n" + str(db.execute(parser.parse(q))))
    print("-" * 50)
