from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    # Setup
    "CREATE TABLE sales (id INT, item STR, price FLOAT)",
    
    # Insert Data
    "INSERT INTO sales VALUES (1, 'Apple', 1.5)",
    "INSERT INTO sales VALUES (2, 'Banana', 0.5)",
    "INSERT INTO sales VALUES (3, 'Orange', 2.0)",
    "INSERT INTO sales VALUES (4, 'Mango', 3.0)",
    
    # Test Time-Series Window Functions!
    "SELECT item, price, RUNNING_TOTAL(price), LAG(price), CUMULATIVE_AVG(price) FROM sales ORDER BY id ASC"
]

for q in queries:
    print("QUERY:", q)
    try:
        res = db.execute(parser.parse(q))
        print("RESULT:\n" + str(res))
    except Exception as e:
        print("EXCEPTION:", str(e))
    print("-" * 50)
