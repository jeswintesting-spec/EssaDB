from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    "CREATE TABLE buffer_test (id INT, name STR)",
]

for q in queries:
    print("QUERY:", q)
    db.execute(parser.parse(q))

# Insert 200 records to test page evictions (assuming each page holds few nodes)
print("Inserting 200 records to fill Buffer Pool...")
for i in range(200):
    db.execute(parser.parse(f"INSERT INTO buffer_test VALUES ({i}, 'Name_{i}')"))

print("Running a search query...")
res = db.execute(parser.parse("SELECT * FROM buffer_test WHERE id = 150"))
print("RESULT:", res)

print("Checking Cache size:", len(db.indexes["buffer_test"][1].pager.cache))
print("Checking Dirty pages:", len(db.indexes["buffer_test"][1].pager.dirty))
