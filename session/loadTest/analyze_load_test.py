#!/usr/bin/env python

# %%
from redis import Redis
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

redis_ip = "127.0.0.1"
redis_port = 6379
r = Redis(host=redis_ip, port=redis_port)

# %%
# Load entries from the publisher
entry_id = b'0-0'
entries = []
replies = r.xread({b'publisher': entry_id})[0][1]
# %%
for reply in replies:
    entry_id, entry_dict = reply
    del entry_dict[b'val']
    entry_dict[b'id'] = entry_id
    entries.append(entry_dict)

# %%
df = pd.DataFrame(entries)
df.rename(columns={col: col.decode() for col in df.columns}, inplace=True)
df['ts'] = df['ts'].astype(float)
df['size'] = df['size'].astype(int)

# %%
latency = df['ts'].diff().values.astype(np.float)[1:] * 1e3
latency = latency[1:]  # remove first entry (NaN)

plt.figure()
plt.hist(latency, bins=np.arange(start=0, stop=max(latency), step=1e-3))

plt.xlabel('Time between successive samples (ms)')
plt.ylabel('Number of Samples')

tbr_std = np.std(latency)
tbr_mean = np.mean(latency)
plt.title('Sampling period: 'f'{tbr_mean :.4f} +- {tbr_std :.4f} ms')

plt.savefig('time_between_readings.png')

# %%
# Load entries from the subscriber
entry_id = b'0-0'
entries = []
replies = r.xread({b'subscriber': entry_id})[0][1]
# %%
for reply in replies:
    entry_id, entry_dict = reply
    entry_dict[b'id'] = entry_id
    entries.append(entry_dict)

df = pd.DataFrame(entries)
df.rename(columns={col: col.decode() for col in df.columns}, inplace=True)
df['ts'] = df['ts'].astype(float)
df['ts_sent'] = df['ts_sent'].astype(float)

# %%
latency = (df['ts'] - df['ts_sent']) * 1e3
latency = latency[1:]  # remove first entry (NaN)

plt.figure()
plt.hist(latency, bins=np.arange(start=0, stop=max(latency), step=1e-3))

plt.xlabel('Time between send and receive (ms)')
plt.ylabel('Number of Samples')

tbr_std = np.std(latency)
tbr_mean = np.mean(latency)
plt.title('Message latency: 'f'{tbr_mean :.4f} +- {tbr_std :.4f} ms')

plt.savefig('message_latency.png')

# %%
