import struct
import os
import json
from datetime import datetime
import threading

class TableStorage:
    """
    Handles reading and writing fixed-size rows to a raw binary .dat file.
    Now includes a 1-byte 'tombstone' header for every record to support fast DELETE.
    """
    def __init__(self, filepath, schema):
        self.filepath = filepath
        self.schema = schema
        if not os.path.exists(self.filepath):
            open(self.filepath, 'w+b').close()
        self.file = open(self.filepath, 'r+b')
        self.record_format = self._build_format()
        self.record_size = struct.calcsize(self.record_format)
        self.io_lock = threading.Lock()

    def _build_format(self):
        # We prefix a 1-byte unsigned char (B) for the tombstone flag
        # 0 = Active, 1 = Deleted
        fmt = '<B'
        for name, dtype in self.schema:
            if dtype == 'INT':
                fmt += 'i'
            elif dtype == 'STR':
                fmt += '64s'
            elif dtype == 'FLOAT':
                fmt += 'f'
            elif dtype == 'BOOL':
                fmt += '?'
            elif dtype == 'JSON':
                fmt += '256s'
            elif dtype == 'DATETIME':
                fmt += '20s'
            elif dtype == 'VECTOR':
                fmt += '512s'
            else:
                raise ValueError(f"Unsupported data type: {dtype}")
        return fmt

    def close(self):
        self.file.close()

    def insert_record(self, record):
        packed = [0] # 0 = Active record
        for i, (name, dtype) in enumerate(self.schema):
            val = record[i]
            if dtype == 'STR':
                if isinstance(val, str):
                    val = val.encode('utf-8')
                val = val[:64].ljust(64, b'\x00')
            elif dtype == 'INT':
                val = int(val)
            elif dtype == 'FLOAT':
                val = float(val)
            elif dtype == 'BOOL':
                val = bool(val)
            elif dtype == 'JSON':
                if isinstance(val, (dict, list)):
                    val = json.dumps(val)
                if isinstance(val, str):
                    val = val.encode('utf-8')
                val = val[:256].ljust(256, b'\x00')
            elif dtype == 'DATETIME':
                if isinstance(val, str):
                    if val.upper() == 'NOW()':
                        val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    val = val.encode('utf-8')
                elif not isinstance(val, bytes):
                    val = str(val).encode('utf-8')
                val = val[:20].ljust(20, b'\x00')
            elif dtype == 'VECTOR':
                if isinstance(val, list):
                    val = json.dumps(val)
                if isinstance(val, str):
                    val = val.encode('utf-8')
                val = val[:512].ljust(512, b'\x00')
            packed.append(val)
        
        data = struct.pack(self.record_format, *packed)
        with self.io_lock:
            self.file.seek(0, 2)
            offset = self.file.tell()
            self.file.write(data)
            self.file.flush()
        return offset

    def update_record(self, offset, new_record):
        # In-place byte replacement! Only possible because records are fixed-size.
        packed = [0]
        for i, (name, dtype) in enumerate(self.schema):
            val = new_record[i]
            if dtype == 'STR':
                if isinstance(val, str):
                    val = val.encode('utf-8')
                val = val[:64].ljust(64, b'\x00')
            elif dtype == 'INT':
                val = int(val)
            elif dtype == 'FLOAT':
                val = float(val)
            elif dtype == 'BOOL':
                val = bool(val)
            elif dtype == 'JSON':
                if isinstance(val, (dict, list)):
                    val = json.dumps(val)
                if isinstance(val, str):
                    val = val.encode('utf-8')
                val = val[:256].ljust(256, b'\x00')
            elif dtype == 'DATETIME':
                if isinstance(val, str):
                    if val.upper() == 'NOW()':
                        val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    val = val.encode('utf-8')
                elif not isinstance(val, bytes):
                    val = str(val).encode('utf-8')
                val = val[:20].ljust(20, b'\x00')
            elif dtype == 'VECTOR':
                if isinstance(val, list):
                    val = json.dumps(val)
                if isinstance(val, str):
                    val = val.encode('utf-8')
                val = val[:512].ljust(512, b'\x00')
            packed.append(val)
        
        data = struct.pack(self.record_format, *packed)
        with self.io_lock:
            self.file.seek(offset)
            self.file.write(data)
            self.file.flush()

    def delete_record(self, offset):
        # We don't shrink the file, we just flip the first byte to 1 (Deleted)
        with self.io_lock:
            self.file.seek(offset)
            self.file.write(struct.pack('<B', 1))
            self.file.flush()
        
    def undelete_record(self, offset):
        # For UNDO: flip the tombstone back to 0 (Active)
        with self.io_lock:
            self.file.seek(offset)
            self.file.write(struct.pack('<B', 0))
            self.file.flush()

    def read_record(self, offset):
        with self.io_lock:
            self.file.seek(offset)
            data = self.file.read(self.record_size)
        if not data or len(data) < self.record_size:
            return None
            
        unpacked = struct.unpack(self.record_format, data)
        if unpacked[0] == 1:
            return None # Record was deleted
            
        result = []
        for i, (name, dtype) in enumerate(self.schema):
            val = unpacked[i + 1] # shift by 1 due to tombstone byte
            if dtype == 'STR':
                val = val.decode('utf-8').rstrip('\x00')
            elif dtype == 'JSON':
                val = val.decode('utf-8').rstrip('\x00')
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    val = None
            elif dtype == 'DATETIME':
                val = val.decode('utf-8').rstrip('\x00')
            elif dtype == 'VECTOR':
                val = val.decode('utf-8').rstrip('\x00')
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    val = []
            result.append(val)
        return tuple(result)
        
    def read_all(self):
        records = []
        offsets = []
        with self.io_lock:
            self.file.seek(0)
            while True:
                offset = self.file.tell()
                data = self.file.read(self.record_size)
                if not data or len(data) < self.record_size:
                    break
                    
                unpacked = struct.unpack(self.record_format, data)
                if unpacked[0] == 1:
                    continue # Skip deleted records
                    
                result = []
                for i, (name, dtype) in enumerate(self.schema):
                    val = unpacked[i + 1]
                    if dtype == 'STR':
                        val = val.decode('utf-8').rstrip('\x00')
                    elif dtype == 'JSON':
                        val = val.decode('utf-8').rstrip('\x00')
                        try:
                            val = json.loads(val)
                        except json.JSONDecodeError:
                            val = None
                    elif dtype == 'DATETIME':
                        val = val.decode('utf-8').rstrip('\x00')
                    elif dtype == 'VECTOR':
                        val = val.decode('utf-8').rstrip('\x00')
                        try:
                            val = json.loads(val)
                        except json.JSONDecodeError:
                            val = []
                    result.append(val)
                records.append(tuple(result))
                offsets.append(offset)
        return records, offsets

    def close(self):
        self.file.close()
