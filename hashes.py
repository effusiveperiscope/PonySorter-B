from config import load_config
from tqdm import tqdm
from pathlib import Path
import mmh3
import json
import os

HASH_SEED = 43
HASHES_FILE = 'hashes.json'

# Unlike the original PonySorter this is just intended for file integrity
# checking, not identification -- the hash is matched against a file name
class Hasher:
    def __init__(self, conf):
        self.conf = conf
        self.hashes = {}
        # We cache these because changing the actual input files while running
        # is out of scope
        self.checked_set = set()
        if os.path.exists(HASHES_FILE):
            with open(HASHES_FILE) as f:
                self.hashes = json.load(f)

    def collect_hashes(self):
        for (root,_,files) in os.walk(self.conf['in_audio_dir']):
            for f in files:
                print(f"Hashing {f}")
                if not f.endswith(self.conf['audio']['file_format']):
                    continue
                f = Path(f).name
                with open(os.path.join(root,f),'rb') as f2:
                    x = f2.read()
                    self.hashes[f] = mmh3.hash128(x, HASH_SEED)
        with open(HASHES_FILE, 'w') as f:
            json.dump(self.hashes, f)

    def check_hash(self, f):
        key = Path(f).name
        if key in self.checked_set:
            return True
        if not key in self.hashes:
            return None
        with open(f, 'rb') as f:
            x = f.read()
        if self.hashes[key] == mmh3.hash128(x, HASH_SEED):
            self.checked_set.add(key)
            return True
        else:
            return False

if __name__ == '__main__':
    conf = load_config()
    h = Hasher(conf)
    h.collect_hashes()