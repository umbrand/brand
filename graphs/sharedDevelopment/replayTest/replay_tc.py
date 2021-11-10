"""
Replay threshold crossings from RDB
"""
# %%
from brand import initializeRedisFromYAML
import time

r = initializeRedisFromYAML('replayTest.yaml')

# %%
# Load data from Redis
# taskInput
stream_entries = r.xread(streams={b'thresholdCrossings': 0})[0][1]

# %%
# replay
duration = 30
sample_rate = 1e3
last_time = 0
i = 0
start_time = time.perf_counter()
# send samples to Redis at the specified sampling rate
while time.perf_counter() - start_time < duration:
    entry = stream_entries[i][1]
    current_time = time.perf_counter()
    if current_time - last_time >= 1 / sample_rate:
        r.xadd(b'tc_replay', entry)
        i += 1
        last_time = current_time

# %%
