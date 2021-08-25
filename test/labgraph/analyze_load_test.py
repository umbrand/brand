# %%
import numpy as np
import h5py
import os
import matplotlib.pyplot as plt
import pandas as pd

try:
    plt.close(plt.figure())
except Exception:
    plt.switch_backend('Agg')

# %%
LOG_FILE = ('/tmp/load_test_python_linux_20210818_111700.h5')

this_dir = os.path.dirname(__file__)
h5_file = os.path.join(this_dir, LOG_FILE)
h5f = h5py.File(h5_file, 'r')

# %%
block_sizes = sorted([
    int(key.split('_')[2]) for key in h5f.keys()
    if key.startswith('sample_summary')
])
# %%
n_bs = len(block_sizes)
ncols = 7
nrows = 3
fig, axes = plt.subplots(nrows=nrows,
                         ncols=ncols,
                         sharex=True,
                         figsize=(ncols * 3, nrows * 3))
for i_block, bs in enumerate(block_sizes):
    ax = axes.ravel()[i_block]
    sample_summary = h5f[f"sample_summary_{bs :d}"]
    latencies = (sample_summary['received_timestamp'] -
                 sample_summary['sent_timestamp'])

    ax.hist(latencies, bins=np.arange(start=0, stop=max(latencies), step=1e-3))
    ax.set_xlabel(f'Send-Receive Latency\n({np.mean(latencies) :.4} '
                  f'+- {np.std(latencies) :.4} s)')
    ax.set_ylabel('Samples')
    ax.set_title(f'Block Size: {bs :d} B')
for i_block in range(i_block + 1, nrows * ncols):
    axes.ravel()[i_block].set_axis_off()

plt.tight_layout()
plt.savefig('latency_distribution.png')

# %%
latency_summary = [None] * len(block_sizes)
for i_block, bs in enumerate(block_sizes):
    block_data = {'block_size': bs}

    sample_summary = h5f[f"sample_summary_{bs :d}"]
    send_latencies = np.diff(sample_summary['sent_timestamp']) * 1e3  # ms
    send_t = sample_summary['sent_timestamp']

    block_data['send_latency_mean'] = np.mean(send_latencies)
    block_data['send_latency_std'] = np.std(send_latencies)
    block_data['send_latency_min'] = np.min(send_latencies)
    block_data['send_latency_max'] = np.max(send_latencies)

    sample_summary = h5f[f"sample_summary_{bs :d}"]
    rec_latencies = np.diff(sample_summary['received_timestamp']) * 1e3  # ms
    rec_t = sample_summary['received_timestamp']

    block_data['receive_latency_mean'] = np.mean(rec_latencies)
    block_data['receive_latency_std'] = np.std(rec_latencies)
    block_data['receive_latency_min'] = np.min(rec_latencies)
    block_data['receive_latency_max'] = np.max(rec_latencies)

    send_rec_latencies = (sample_summary['received_timestamp'] -
                          sample_summary['sent_timestamp']) * 1e3

    block_data['send_receive_latency_mean'] = np.mean(send_rec_latencies)
    block_data['send_receive_latency_std'] = np.std(send_rec_latencies)
    block_data['send_receive_latency_min'] = np.min(send_rec_latencies)
    block_data['send_receive_latency_max'] = np.max(send_rec_latencies)

    latency_summary[i_block] = block_data
# %%
latency_df = pd.DataFrame(latency_summary)

# %%
# mask
MiB = 1024**2
b_mask = latency_df['block_size'] < 0.5 * MiB

# %%
fields = [
    'send_latency',
    'receive_latency',
    'send_receive_latency',
]
labels = [
    'Time between sends', 'Time between receives',
    'Time between send and receive'
]
# shading the standard deviation
fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(10, 18), sharey=False)
for i_ax, (field, label) in enumerate(zip(fields, labels)):
    ax = axes[i_ax]
    ax.plot(latency_df.index[b_mask], latency_df[f'{field}_mean'][b_mask])
    ax.fill_between(latency_df.index[b_mask],
                    latency_df[f'{field}_mean'][b_mask] - latency_df[f'{field}_std'][b_mask],
                    latency_df[f'{field}_mean'][b_mask] + latency_df[f'{field}_std'][b_mask],
                    alpha=0.5)
    ax.set_xticks(latency_df.index[b_mask])
    ax.set_xticklabels(latency_df['block_size'], rotation=90)
    ax.set_xlabel('Block Size (bytes)')
    ax.set_ylabel('Mean Latency (milliseconds)\n(shading: standard deviation)')
    ax.set_title(label)

plt.tight_layout()
plt.subplots_adjust(top=0.95)
plt.suptitle('Shading: standard deviation')
plt.savefig('latency_by_block_size_std.png')
# %%
# Shading the full range of data
fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(10, 18), sharey=False)
for i_ax, (field, label) in enumerate(zip(fields, labels)):
    ax = axes[i_ax]
    ax.plot(latency_df.index[b_mask], latency_df[f'{field}_mean'][b_mask])
    ax.fill_between(latency_df.index[b_mask],
                    latency_df[f'{field}_min'][b_mask],
                    latency_df[f'{field}_max'][b_mask],
                    alpha=0.5)
    ax.set_xticks(latency_df.index[b_mask])
    ax.set_xticklabels(latency_df['block_size'], rotation=90)
    ax.set_xlabel('Block Size (bytes)')
    ax.set_ylabel('Mean Latency (milliseconds)\n(shading: min to max)')
    ax.set_title(label)

plt.tight_layout()
plt.subplots_adjust(top=0.95)
plt.suptitle('Shading: min to max')
plt.savefig('latency_by_block_size_range.png')
# %%
latency_df.to_csv('labgraph_latencies.csv')
# %%
