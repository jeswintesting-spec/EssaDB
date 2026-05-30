from engine import DatabaseEngine
from parser import QueryParser
import os
import shutil

if os.path.exists("./data"): shutil.rmtree("./data")

db = DatabaseEngine("./data")
parser = QueryParser()

queries = [
    # Setup Vector Table
    "CREATE TABLE documents (id INT, title STR, embedding VECTOR)",
    
    # Insert ML Embeddings
    "INSERT INTO documents VALUES (1, 'Machine Learning', [0.9, 0.8, 0.1])",
    "INSERT INTO documents VALUES (2, 'Cooking Pasta', [0.1, 0.0, 0.9])",
    "INSERT INTO documents VALUES (3, 'Deep Neural Networks', [0.8, 0.9, 0.2])",
    
    # Run Cosine Similarity Search
    "SELECT * FROM documents ORDER BY SIMILARITY(embedding, [1.0, 1.0, 0.0]) DESC LIMIT 2"
]

for q in queries:
    print("QUERY:", q)
    try:
        res = db.execute(parser.parse(q))
        print("RESULT:\n" + str(res))
    except Exception as e:
        print("EXCEPTION:", str(e))
    print("-" * 50)
