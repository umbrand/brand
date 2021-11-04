# %%
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from brand import initializeRedisFromYAML

from utils import timeval_to_datetime

# %%
# Connect to Redis
r = initializeRedisFromYAML('replayTest.yaml')
# %%
# Get a list of streams in the database
_, streams = r.scan(_type='STREAM')
# %%
# Get the first entry of each stream
stream_dict = {stream: 0 for stream in streams}
all_entries = r.xread(stream_dict, count=1)

# %%
# List out the streams and their contents
SAVE = True
f = sys.stdout if not SAVE else open('streams.txt', 'w')
for stream, stream_entries in all_entries:
    print(f'{stream.decode()}:', file=f)
    for key, val in stream_entries[0][1].items():
        print(f'\t{key.decode()}: {len(val)} {type(val).__name__}', file=f)
if SAVE:
    f.close()

# %%
# Load example entries for each stream into a dictionary
stream_examples = {}
for stream, stream_entries in all_entries:
    stream_examples[stream.decode()] = stream_entries[0][1]

# %%
# Decode stream entries
with open('stream_spec.yaml', 'r') as f:
    stream_spec = yaml.safe_load(f)

ds = decoded_streams = {}
for stream, stream_keys in stream_spec.items():
    ex = stream_examples[stream]
    ds[stream] = {}
    for key, dtype in stream_keys.items():
        entry = ex[key.encode()]
        if dtype == 'str':
            ds[stream][key] = entry.decode()
        elif dtype == 'float':
            ds[stream][key] = float(entry)
        elif dtype == 'bool':
            ds[stream][key] = bool(entry)
        elif dtype == 'timeval':
            n_bytes = len(entry)
            n_items = int(n_bytes / 16)
            if n_items == 1:
                ds[stream][key] = timeval_to_datetime(entry).timestamp()
            else:
                vals = np.zeros(n_items)
                for ii in range(n_items):
                    a, b = (ii * 16, (ii + 1) * 16)
                    vals[ii] = timeval_to_datetime(entry[a:b]).timestamp()
        else:
            ds[stream][key] = np.frombuffer(entry, dtype=dtype)
            if len(ds[stream][key]) == 1:
                ds[stream][key] = ds[stream][key].item()
decoded_streams

# %%
from datetime import datetime

datetime.fromtimestamp(decoded_streams['taskInput']['BRANDS_time'])

# %%
decoded_streams['cursorData']['sync']
# %%
decoded_streams['thresholdCrossings']['timestamps']
# %%
