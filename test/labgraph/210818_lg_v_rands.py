# %%
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42

# LabGraph data
lgdf = pd.read_csv('data/labgraph_latencies_1000Hz.csv', index_col=0)
8 * lgdf['block_size']
# RANDS data
rdf = pd.read_csv('data/rands_latencies.csv', index_col=0)

# %%
block_sizes = sorted(rdf['block_size'].values)

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
    fig, axes = plt.subplots(ncols=1, nrows=3, figsize=(10, 18), sharey=False)
    for i_ax, (field, label) in enumerate(zip(fields, labels)):
        ax = axes[i_ax]

        for df, lbl in [[lgdf, 'LabGraph'], [rdf, 'RANDS']]:
            ax.plot(np.arange(len(df.index)),
                    df[f'{field}_mean'],
                    'o-',
                    label=lbl)
            if fill in ['std', 'standard deviation']:
                ax.fill_between(np.arange(len(df.index)),
                                df[f'{field}_mean'] - df[f'{field}_std'],
                                df[f'{field}_mean'] + df[f'{field}_std'],
                                alpha=0.25)
            else:
                ax.fill_between(np.arange(len(df.index)),
                                df[f'{field}_min'],
                                df[f'{field}_max'],
                                alpha=0.25)
            ax.set_xticks(np.arange(len(df.index)))
            ax.set_xticklabels(df['block_size'], rotation=45)
            ax.set_xlabel('Number of uint64 array elements')
            ax.set_ylabel('Mean Latency (ms)')
            ax.set_ylim([None, 20])
            ax.set_title(label)
            ax.legend()

    plt.tight_layout()
    plt.subplots_adjust(top=0.95)
    plt.suptitle(f'Pub-Sub Latency, Shading: {fill}')
    plt.savefig(f"lg_v_rands_latency_{fill.replace(' ', '_')}.pdf")
# %%
