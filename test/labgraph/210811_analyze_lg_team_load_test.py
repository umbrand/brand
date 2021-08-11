# %%
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# %%
ldf = pd.read_csv('labgraph_latencies_official.csv')
platforms = ldf['platform'].unique()
languages = ldf['language'].unique()

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
# shading the standard deviation
for language in languages:
    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(10, 18), sharey=False)
    for i_ax, (field, label) in enumerate(zip(fields, labels)):
        ax = axes[i_ax]

        for platform in platforms:
            pl_mask = (ldf['platform'] == platform,
                       ldf['language'] == language)
            mask = np.all((b_mask, *pl_mask), axis=0)
            ax.plot(np.arange(len(ldf.index[mask])),
                    ldf[f'{field}_mean'][mask],
                    'o-',
                    label=f'{platform}, {language}')
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
    plt.suptitle(f'Language: {language}, Shading: {fill}')
    plt.savefig(f"cross_platform_latency_{fill.replace(' ', '_')}"
                f"_{language}.png")
# %%
