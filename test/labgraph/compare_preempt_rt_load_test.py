# %%
import pandas as pd
import matplotlib.pyplot as plt


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
VANILLA_KERNEL_RESULTS = 'labgraph_latencies_ubuntu.csv'
PREEMPT_RT_KERNEL_RESULTS = 'labgraph_latencies_ubuntu_preempt_rt.csv'

vdf = pd.read_csv(VANILLA_KERNEL_RESULTS, index_col=0)
rdf = pd.read_csv(PREEMPT_RT_KERNEL_RESULTS, index_col=0)

# %%
fields = [val for val in vdf.columns.values if val not in ['block_size']]
ncols, nrows = 3, 4
fig, axes = plt.subplots(ncols=ncols,
                         nrows=nrows,
                         figsize=(ncols * 6, nrows * 5),
                         sharey='row')
for ifield, field in enumerate(fields):
    ax = axes.T.ravel()[ifield]
    ax.plot(vdf.index, vdf[field], 'o-', label='Vanilla Kernel')
    ax.plot(vdf.index, rdf[field], 'o-', label='PREEMPT_RT Kernel')
    ax.set_xticks(vdf.index)
    ax.set_xticklabels(vdf['block_size'], rotation=90)
    ax.set_ylabel(label_maker(field))
    ax.set_xlabel('Block Size (bytes)')
    ax.legend()
plt.tight_layout()
plt.savefig('preempt_rt_metrics.png')
