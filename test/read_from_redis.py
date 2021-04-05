# %%
from datetime import datetime
from struct import pack, unpack
from redis import Redis
import ctypes
from ctypes import Structure, c_long

class timeval(Structure):
    """
    timeval struct from sys/time.h
    """
    _fields_ = [("tv_sec", c_long), ("tv_usec", c_long)]

# %%
# Connect to Redis
redis_ip = "127.0.0.1"
redis_port = 6379
r = Redis(host = redis_ip, port = redis_port)

# %%
# Read the latest entry in the stream
cursorFrame = r.xread({b'mouse_ac':'$'}, count=1, block=0)[0][1][0][1]

# Unpack the x y positions of the cursor
unpackString = '2h'
x_pos, y_pos = unpack(unpackString, cursorFrame[b'samples'])

# Unpack the timestamp
ts = timeval.from_buffer_copy(cursorFrame[b'timestamps'])
timestamp = datetime.fromtimestamp(ts.tv_sec + ts.tv_usec * 1e-6)
# %%
