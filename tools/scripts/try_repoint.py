"""Try re-pointing one character's Hat sprite, render it, then restore.

Re-pointing is geometry-safe only when the source and target sprite share
rect/offset/PPU.  When they do not, the art lands somewhere else on the head --
so this probe patches, renders, and puts the original 8 bytes back, letting the
result be judged before anything is committed.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA

SR = int(sys.argv[1])
NEW_PID = int(sys.argv[2])
KEEP = "--keep" in sys.argv

db = AssetDB(data_dir=DATA)
obj = db.file_objs("resources.assets").get(SR)
cur = obj.read_typetree().get("m_Sprite") or {}
fid, pid = cur.get("m_FileID", 0), cur.get("m_PathID", 0)
path = os.path.join(DATA, "resources.assets")
with open(path, "rb") as fh:
    fh.seek(int(obj.byte_start))
    blob = fh.read(int(obj.byte_size))
hits = [i for i in range(len(blob) - 7)
        if blob[i:i + 8] == struct.pack("<ii", fid, pid)]
assert len(hits) == 1, hits
off = int(obj.byte_start) + hits[0]

save = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "_pptr_save.bin")
if KEEP:
    with open(save, "rb") as fh:
        old = fh.read()
    with open(path, "r+b") as fh:
        fh.seek(off)
        fh.write(old)
    print(f"SR#{SR} restored to {struct.unpack('<ii', old)}")
else:
    with open(path, "rb") as fh:
        fh.seek(off)
        old = fh.read(8)
    with open(save, "wb") as fh:
        fh.write(old)
    with open(path, "r+b") as fh:
        fh.seek(off)
        fh.write(struct.pack("<ii", 0, NEW_PID))
    print(f"SR#{SR} {(fid, pid)} -> (0, {NEW_PID});  saved {struct.unpack('<ii', old)}")
