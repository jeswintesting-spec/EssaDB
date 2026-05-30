import os
import shutil
import time
from engine import DatabaseEngine
from parser import QueryParser
from wal import WriteAheadLog

if os.path.exists("./data"):
    shutil.rmtree("./data")

print("--- Step 1: Initialize DB and run operations ---")
db = DatabaseEngine("./data")
parser = QueryParser()

# Create table
db.execute(parser.parse("CREATE TABLE users (id INT, name STR)"))

# Insert Alice
db.execute(parser.parse("INSERT INTO users VALUES (1, 'Alice')"))

print("Current Users in DB:")
print(db.execute(parser.parse("SELECT * FROM users")))

print("\n--- Step 2: Simulating a CRASH mid-transaction ---")
print("We will write to the WAL, but simulate a power loss before it writes to the .dat file.")

# Manually write an uncommitted transaction to the WAL to simulate a crash
# In reality, this happens if the server loses power exactly between WAL flush and .dat write.
wal = WriteAheadLog("./data/essadb.wal")
fake_query = parser.parse("INSERT INTO users VALUES (2, 'Bob (Recovered from crash!)')")
wal.begin_transaction(fake_query)
# Notice we DO NOT call commit_transaction! The power went out!

print("Power went out! Bob is NOT in the .dat file yet.")

print("\n--- Step 3: Rebooting the Server ---")
time.sleep(1)

# Start engine again. It should read the WAL and automatically replay the lost transaction!
db2 = DatabaseEngine("./data")

print("Current Users in DB (Notice Bob was recovered!):")
print(db2.execute(parser.parse("SELECT * FROM users")))
