import ast
import zlib

from utilities.blobs import blob_unserialize, blob_dump

def read_secondblob(filepath):
    with open(filepath, "rb") as f :
        blob = f.read( )
    if blob[0:2] == b"\x01\x43" :
        blob = zlib.decompress(blob[20 :])
    firstblob_unser = blob_unserialize(blob)
    firstblob = "blob = " + blob_dump(firstblob_unser)
    blob_dict = ast.literal_eval(firstblob[7:len(firstblob)])
    return blob_dict