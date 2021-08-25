# %%
import os

import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm.auto import tqdm


def label_maker(lbl):
    if lbl.startswith('send_latency'):
        desc = 'time between sends'
    elif lbl.startswith('receive_latency'):
        desc = 'time between receives'
    elif lbl.startswith('send_receive_latency'):
        desc = 'time between send and receive'
    else:
        return lbl.replace('_', ' ')

    metric = lbl.split('_')[-1]
    if metric == 'std':
        metric = 'standard deviation'

    return f'{metric} {desc}'.title() + ' (ms)'


# %%

log_files = [
    'load_test_python_linux_20210813_085811_1000Hz_async.h5',
    'load_test_python_linux_20210813_092102_1000Hz.h5'
]
methods = ['asyncio.sleep', 'if-statement']
latency_summaries = []
for log_file, method in zip(log_files, methods):
    # load data
    this_dir = os.path.dirname(__file__)
    h5_file = os.path.join(this_dir, 'load_test_results', log_file)
    with h5py.File(h5_file, 'r') as h5f:
        block_sizes = sorted([
            int(key.split('_')[2]) for key in h5f.keys()
            if key.startswith('sample_summary')
        ])

        # create a list of dictionaries with summary stats on latencies
        latency_summary = [None] * len(block_sizes)
        for i_block, bs in enumerate(tqdm(block_sizes)):
            block_data = {'block_size': bs}

            # compute latencies
            summary = h5f[f"sample_summary_{bs :d}"]
            send_latencies = np.diff(summary['sent_timestamp']) * 1e3  # ms
            rec_latencies = np.diff(summary['received_timestamp']) * 1e3  # ms
            send_rec_latencies = (summary['received_timestamp'] -
                                  summary['sent_timestamp']) * 1e3  # ms

            # compute summary statistics
            for ldata, field in [[send_latencies, 'send_latency'],
                                 [rec_latencies, 'receive_latency'],
                                 [send_rec_latencies, 'send_receive_latency']]:
                block_data[f'{field}_mean'] = np.mean(ldata)
                block_data[f'{field}_std'] = np.std(ldata)
                block_data[f'{field}_min'] = np.min(ldata)
                block_data[f'{field}_max'] = np.max(ldata)

            # add language and method information from the filename
            block_data['method'] = method

            latency_summary[i_block] = block_data
    latency_summaries += latency_summary

ldf = pd.DataFrame(latency_summaries)

# %%
# %%
# mask
MiB = 1024**2
b_mask = ldf['block_size'] < 0.5 * MiB

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
fill = 'standard deviation'

fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(10, 18), sharey=False)
for i_ax, (field, label) in enumerate(zip(fields, labels)):
    ax = axes[i_ax]

    for method in methods:
        pl_mask = ldf['method'] == method
        mask = np.all((b_mask, pl_mask), axis=0)
        ax.plot(np.arange(len(ldf.index[mask])),
                ldf[f'{field}_mean'][mask],
                'o-',
                label=method)
        if fill in ['std', 'standard deviation']:
            ax.fill_between(
                np.arange(len(ldf.index[mask])),
                ldf[f'{field}_mean'][mask] - ldf[f'{field}_std'][mask],
                ldf[f'{field}_mean'][mask] + ldf[f'{field}_std'][mask],
                alpha=0.25)
        else:
            ax.fill_between(np.arange(len(ldf.index[mask])),
                            ldf[f'{field}_min'][mask],
                            ldf[f'{field}_max'][mask],
                            alpha=0.25)
    ax.set_xticks(np.arange(len(ldf.index[mask])))
    ax.set_xticklabels(ldf['block_size'][mask], rotation=90)
    ax.set_xlabel('Block Size (bytes)')
    ax.set_ylabel(f'Mean Latency (milliseconds)\n(shading: {fill})')
    ax.set_title(label)
    ax.legend()

plt.tight_layout()
plt.subplots_adjust(top=0.95)
plt.suptitle(f'Shading: {fill}')
plt.savefig(f"fixed_rate_latency_{fill.replace(' ', '_')}.png")


# %%
