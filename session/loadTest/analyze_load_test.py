#!/usr/bin/env python

# %%
from redis import Redis
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

redis_ip = "127.0.0.1"
redis_port = 6379

# %%
# Load entries from the subscriber
entry_id = b'0-0'
entries = []
r = Redis(host=redis_ip, port=redis_port)
replies = r.xread({b'subscriber': entry_id})[0][1]
r.close()

for reply in replies:
    entry_id, entry_dict = reply
    entries.append(entry_dict)

sdf = pd.DataFrame(entries)
sdf.rename(columns={col: col.decode() for col in sdf.columns}, inplace=True)
sdf['ts'] = sdf['ts'].astype(float)
sdf['ts_sent'] = sdf['ts_sent'].astype(float)
sdf['size'] = sdf['size'].astype(int)
sdf['counter'] = sdf['counter'].astype(int)
# %%
# construct dataframe with summary statistics
# load data
block_sizes = sdf['size'].unique()

# create a list of dictionaries with summary stats on latencies
latency_summary = [None] * len(block_sizes)
for i_block, bs in enumerate(block_sizes):
    block_data = {'block_size': bs}
    mask = sdf['size'] == bs

    # compute latencies
    send_latencies = np.diff(sdf['ts_sent'][mask]) * 1e3  # ms
    rec_latencies = np.diff(sdf['ts'][mask]) * 1e3  # ms
    send_rec_latencies = (sdf['ts'][mask] - sdf['ts_sent'][mask]) * 1e3  # ms

    # compute summary statistics
    for ldata, field in [[send_latencies, 'send_latency'],
                         [rec_latencies, 'receive_latency'],
                         [send_rec_latencies, 'send_receive_latency']]:
        block_data[f'{field}_mean'] = np.mean(ldata)
        block_data[f'{field}_std'] = np.std(ldata)
        block_data[f'{field}_min'] = np.min(ldata)
        block_data[f'{field}_max'] = np.max(ldata)

    block_data['missed_samples'] = np.sum(np.diff(sdf['counter'][mask]) - 1)
    block_data['total_samples'] = sdf['counter'][mask].values[-1]

    latency_summary[i_block] = block_data

# %%
ldf = pd.DataFrame(latency_summary)
ldf.to_csv('rands_latencies.csv')

# %%
# plots
try:
    plt.close(plt.figure())
except Exception:
    plt.switch_backend('Agg')

fields = [
    'send_latency',
    'receive_latency',
    'send_receive_latency',
]
labels = [
    'Time between sends', 'Time between receives',
    'Time between send and receive'
]
fill = 'standard deviation'
# shading the standard deviation

fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(10, 24), sharey=False)
for i_ax, (field, label) in enumerate(zip(fields, labels)):
    ax = axes[i_ax]

    ax.plot(np.arange(len(ldf.index)), ldf[f'{field}_mean'], 'o-')
    if fill in ['std', 'standard deviation']:
        ax.fill_between(np.arange(len(ldf.index)),
                        ldf[f'{field}_mean'] - ldf[f'{field}_std'],
                        ldf[f'{field}_mean'] + ldf[f'{field}_std'],
                        alpha=0.25)
    else:
        ax.fill_between(np.arange(len(ldf.index)),
                        ldf[f'{field}_min'],
                        ldf[f'{field}_max'],
                        alpha=0.25)
    ax.set_xticks(np.arange(len(ldf.index)))
    ax.set_xticklabels(ldf['block_size'], rotation=45)
    ax.set_xlabel('Number of int16 array elements')
    ax.set_ylabel(f'Mean Latency (milliseconds)\n(shading: {fill})')
    ax.set_title(label)

ax = axes[i_ax + 1]
ax.plot(ldf.index, ldf['missed_samples'], 'o-')
ax.set_xticks(np.arange(len(ldf.index)))
ax.set_xticklabels(ldf['block_size'], rotation=45)
ax.set_xlabel('Number of int16 array elements')
ax.set_ylabel('Number of missed samples')
ax.set_title('Missed Samples')

plt.tight_layout()
plt.subplots_adjust(top=0.95)
plt.suptitle(f'Redis Pub-Sub Latency, Shading: {fill}')
plt.savefig(f"latency_{fill.replace(' ', '_')}.png")
# %%

# %%
