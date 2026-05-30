import os
import json
import uuid

class WriteAheadLog:
    """
    Implements a logical Write-Ahead Log (WAL) to guarantee ACID Durability.
    Operations are fsync'd to disk before they are applied to the actual database files.
    """
    def __init__(self, filepath):
        self.filepath = filepath
        self.file = open(self.filepath, 'a+')

    def begin_transaction(self, parsed_query):
        """
        Logs that a transaction is about to begin.
        """
        tx_id = str(uuid.uuid4())
        entry = json.dumps({"tx_id": tx_id, "status": "START", "query": parsed_query}) + "\n"
        self.file.write(entry)
        self.file.flush()
        os.fsync(self.file.fileno()) # Force physical disk write!
        return tx_id

    def commit_transaction(self, tx_id):
        """
        Logs that a transaction successfully completed writing to .dat and .idx files.
        """
        entry = json.dumps({"tx_id": tx_id, "status": "COMMIT"}) + "\n"
        self.file.write(entry)
        self.file.flush()
        os.fsync(self.file.fileno())

    def get_uncommitted_transactions(self):
        """
        Scans the WAL on startup to find queries that crashed mid-execution.
        """
        self.file.seek(0)
        started = {}
        committed = set()
        
        for line in self.file:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                tx_id = data["tx_id"]
                if data["status"] == "START":
                    started[tx_id] = data["query"]
                elif data["status"] == "COMMIT":
                    committed.add(tx_id)
            except json.JSONDecodeError:
                pass # Corrupt line from sudden power loss
                
        # Find transactions that started but never committed
        uncommitted = []
        for tx_id, query in started.items():
            if tx_id not in committed:
                uncommitted.append(query)
                
        return uncommitted

    def clear(self):
        """
        Truncates the WAL. In a real DB, this happens during 'Checkpointing'.
        """
        self.file.seek(0)
        self.file.truncate()
        self.file.flush()
        os.fsync(self.file.fileno())
