#!/usr/bin/env python

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ldf = pd.read_csv('rands_latencies_maxlen.csv', index_col=0)

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
for fill in ['standard deviation', 'min-max']:
    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(10, 18), sharey=False)
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
        ax.ticklabel_format(useOffset=False)
        ax.set_xticks(np.arange(len(ldf.index)))
        ax.set_xticklabels(ldf['maxlen'], rotation=45)
        ax.set_xlabel('MAXLEN')
        ax.set_ylabel(f'Mean Latency (milliseconds)\n(shading: {fill})')
        ax.set_title(label)

    plt.tight_layout()
    plt.subplots_adjust(top=0.95)
    plt.suptitle(f'Redis Pub-Sub Latency, Shading: {fill}')
    plt.savefig(f"latency_{fill.replace(' ', '_')}.png")
# %%

# %%
