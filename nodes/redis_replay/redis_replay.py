"""
Replay threshold crossings from RDB
"""
# %%
import logging
import sys
import time
from utils import load_stream
import yaml
import numpy as np

from brand import (config_logging, get_node_parameter_value,
                   initializeRedisFromYAML)

NAME = 'redis_replay'
YAML_FILE = sys.argv[1] if len(sys.argv) > 1 else f'{NAME}.yaml'
YAML_FILE = f'{NAME}.yaml'
r = initializeRedisFromYAML(YAML_FILE, NAME)

DURATION = get_node_parameter_value(YAML_FILE, NAME, 'duration')
SAMPLE_RATE = get_node_parameter_value(YAML_FILE, NAME, 'sample_rate')
LOGLEVEL = get_node_parameter_value(YAML_FILE, NAME, 'log')
config_logging(NAME, LOGLEVEL)

# %%
# Account for gaps in the cerebus timestamps
with open('stream_spec.yaml', 'r') as f:
    stream_spec = yaml.safe_load(f)

df = load_stream(r, 'thresholdCrossings', stream_spec)

ts_diff = np.diff(df['timestamps'])
ts_diff[ts_diff > 30]
indices = np.arange(df['timestamps'].shape[0])
# beginning of the last continuous chunk of data
start = indices[1:][ts_diff > 30][-1]

# %%
# Load data from Redis
# taskInput
stream_entries = r.xread(streams={b'thresholdCrossings': 0})[0][1]

# %%
# # send samples to Redis at the specified sampling rate
last_time = 0  # last time a sample was replayed
i = start  # index of the first entry in the stream
sample_interval = 1 / SAMPLE_RATE
logging.info('Sending samples')
start_time = time.time()
while time.time() - start_time < DURATION:
    entry = stream_entries[i][1]
    current_time = time.time()
    if current_time - last_time >= sample_interval:
        entry['ts'] = current_time
        r.xadd(b'tc_replay', entry)
        i += 1
        last_time = current_time
    if i == len(stream_entries):
        break

# %%
