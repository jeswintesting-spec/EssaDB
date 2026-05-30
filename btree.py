import struct
import os
import threading
from collections import OrderedDict

PAGE_SIZE = 4096

class Pager:
    """
    Manages reading and writing fixed-size 4KB pages to a binary file.
    Implements an LRU Buffer Pool to cache up to 100 pages in memory,
    reducing disk I/O significantly.
    """
    def __init__(self, filename, cache_size=100):
        self.filename = filename
        if not os.path.exists(filename):
            open(filename, 'w+b').close()
        self.file = open(filename, 'r+b')
        self.file.seek(0, 2)
        self.num_pages = self.file.tell() // PAGE_SIZE
        
        self.cache_size = cache_size
        self.cache = OrderedDict()
        self.dirty = set()
        self.io_lock = threading.Lock()

    def get_page(self, page_num):
        if page_num in self.cache:
            self.cache.move_to_end(page_num)
            return self.cache[page_num]
            
        if page_num >= self.num_pages:
            data = bytearray(PAGE_SIZE)
        else:
            data = self._read_page(page_num)
            
        self.cache[page_num] = data
        if len(self.cache) > self.cache_size:
            self._evict_lru()
        return data

    def write_page(self, page_num, page_data):
        if page_num in self.cache:
            self.cache.move_to_end(page_num)
        self.cache[page_num] = page_data
        self.dirty.add(page_num)
        
        if len(self.cache) > self.cache_size:
            self._evict_lru()

    def _read_page(self, page_num):
        with self.io_lock:
            self.file.seek(page_num * PAGE_SIZE)
            return bytearray(self.file.read(PAGE_SIZE))

    def _write_page(self, page_num, data):
        with self.io_lock:
            self.file.seek(page_num * PAGE_SIZE)
            self.file.write(data)

    def _evict_lru(self):
        evicted_num, evicted_data = self.cache.popitem(last=False)
        if evicted_num in self.dirty:
            with self.io_lock:
                self.file.seek(evicted_num * PAGE_SIZE)
                self.file.write(evicted_data)
            self.dirty.remove(evicted_num)

    def get_new_page(self):
        page_num = self.num_pages
        self.num_pages += 1
        self.write_page(page_num, bytearray(PAGE_SIZE))
        return page_num

    def flush_all(self):
        with self.io_lock:
            for page_num in list(self.dirty):
                self.file.seek(page_num * PAGE_SIZE)
                self.file.write(self.cache[page_num])
                self.dirty.remove(page_num)
            self.file.flush()

    def close(self):
        self.flush_all()
        self.file.close()


class DiskBTreeNode:
    def __init__(self, pager, page_num):
        self.pager = pager
        self.page_num = page_num
        self.is_leaf = False
        self.is_root = False
        self.keys = []
        self.values = []
        self.children = []
        self.parent = 0

    def load(self):
        data = self.pager.get_page(self.page_num)
        # Header: <BBHI -> is_leaf(1), is_root(1), num_keys(2), parent(4)
        header = struct.unpack('<BBHI', data[:8])
        self.is_leaf = bool(header[0])
        self.is_root = bool(header[1])
        num_keys = header[2]
        self.parent = header[3]

        offset = 8
        if num_keys > 0:
            self.keys = list(struct.unpack(f'<{num_keys}i', data[offset:offset + 4*num_keys]))
            offset += 4 * num_keys
            self.values = list(struct.unpack(f'<{num_keys}I', data[offset:offset + 4*num_keys]))
            offset += 4 * num_keys
        else:
            self.keys = []
            self.values = []
        
        if not self.is_leaf and num_keys > 0:
            # An internal node has num_keys + 1 children
            self.children = list(struct.unpack(f'<{num_keys + 1}I', data[offset:offset + 4*(num_keys+1)]))
        else:
            self.children = []

    def save(self):
        num_keys = len(self.keys)
        header = struct.pack('<BBHI', int(self.is_leaf), int(self.is_root), num_keys, self.parent)
        
        keys_data = b''
        values_data = b''
        if num_keys > 0:
            keys_data = struct.pack(f'<{num_keys}i', *self.keys)
            values_data = struct.pack(f'<{num_keys}I', *self.values)
        
        children_data = b''
        if not self.is_leaf and len(self.children) > 0:
            children_data = struct.pack(f'<{len(self.children)}I', *self.children)
            
        data = header + keys_data + values_data + children_data
        data = data.ljust(PAGE_SIZE, b'\x00') # Pad out exactly to 4096 bytes
        self.pager.write_page(self.page_num, data)


class BTree:
    """
    Disk-backed B-Tree.
    Nodes are read/written to a binary .idx file in 4KB chunks, exactly like real databases.
    """
    def __init__(self, filename, t=50):
        self.pager = Pager(filename)
        if self.pager.num_pages == 0:
            # Create Meta Page (Page 0)
            self.pager.get_new_page()
            # Create Root Page (Page 1)
            self.root_page_num = self.pager.get_new_page()
            self.t = t
            self._save_meta()
            
            root = DiskBTreeNode(self.pager, self.root_page_num)
            root.is_leaf = True
            root.is_root = True
            root.save()
        else:
            self._load_meta()

    def _save_meta(self):
        # Page 0 holds metadata
        data = struct.pack('<II', self.root_page_num, self.t)
        data = data.ljust(PAGE_SIZE, b'\x00')
        self.pager.write_page(0, data)

    def _load_meta(self):
        data = self.pager.get_page(0)
        self.root_page_num, self.t = struct.unpack('<II', data[:8])

    def flush(self):
        self.pager.flush_all()

    def close(self):
        self.pager.close()

    def get_node(self, page_num):
        node = DiskBTreeNode(self.pager, page_num)
        node.load()
        return node

    def search(self, key, node=None):
        if node is None:
            node = self.get_node(self.root_page_num)
        i = 0
        while i < len(node.keys) and key > node.keys[i]:
            i += 1
        if i < len(node.keys) and key == node.keys[i]:
            return node.values[i]
        elif node.is_leaf:
            return None
        else:
            child_node = self.get_node(node.children[i])
            return self.search(key, child_node)

    def insert(self, key, value):
        root = self.get_node(self.root_page_num)
        if len(root.keys) == (2 * self.t) - 1:
            # Split root
            new_root_page = self.pager.get_new_page()
            new_root = DiskBTreeNode(self.pager, new_root_page)
            new_root.is_leaf = False
            new_root.is_root = True
            new_root.children.append(self.root_page_num)
            
            root.is_root = False
            root.parent = new_root_page
            root.save()
            
            self._split_child(new_root, 0, root)
            
            self.root_page_num = new_root_page
            self._save_meta()
            
            self._insert_non_full(new_root, key, value)
        else:
            self._insert_non_full(root, key, value)

    def _insert_non_full(self, node, key, value):
        i = len(node.keys) - 1
        if node.is_leaf:
            node.keys.append(None)
            node.values.append(None)
            while i >= 0 and key < node.keys[i]:
                node.keys[i + 1] = node.keys[i]
                node.values[i + 1] = node.values[i]
                i -= 1
            node.keys[i + 1] = key
            node.values[i + 1] = value
            node.save()
        else:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            i += 1
            
            child = self.get_node(node.children[i])
            if len(child.keys) == (2 * self.t) - 1:
                self._split_child(node, i, child)
                if key > node.keys[i]:
                    i += 1
                child = self.get_node(node.children[i])
            
            self._insert_non_full(child, key, value)

    def _split_child(self, parent, i, y):
        t = self.t
        z_page = self.pager.get_new_page()
        z = DiskBTreeNode(self.pager, z_page)
        z.is_leaf = y.is_leaf
        z.parent = parent.page_num
        
        parent.children.insert(i + 1, z_page)
        parent.keys.insert(i, y.keys[t - 1])
        parent.values.insert(i, y.values[t - 1])
        
        z.keys = y.keys[t: (2 * t - 1)]
        z.values = y.values[t: (2 * t - 1)]
        y.keys = y.keys[0: t - 1]
        y.values = y.values[0: t - 1]
        
        if not y.is_leaf:
            z.children = y.children[t: 2 * t]
            y.children = y.children[0: t]
            
            for child_page in z.children:
                c = self.get_node(child_page)
                c.parent = z_page
                c.save()
        
        y.save()
        z.save()
        parent.save()
