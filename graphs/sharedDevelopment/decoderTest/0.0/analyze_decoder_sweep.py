#!/usr/bin/env python

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from brand import get_node_parameter_value

try:
    plt.close(plt.figure())
except Exception:
    plt.switch_backend('Agg')

# %%
# Get run info
YAML_FILE = 'decoderTest.yaml'

sample_rate = get_node_parameter_value(YAML_FILE, 'func_generator',
                                       'sample_rate')
decoder_type = get_node_parameter_value(YAML_FILE, 'decoder', 'decoder_type')

# %%
# Load entries from csv
csv_file = '211027T2037_timestamps_200Hz.csv'
udf = pd.read_csv(csv_file)

# %%
data = {'decoder': [], 'udp_send': [], 'total': []}
labels = []
for n_features in udf['n_features'].unique():
    mask = udf['n_features'] == n_features
    m_udf = udf[mask]
    data['decoder'].append((m_udf['ts_dec'] - m_udf['ts_gen']).values * 1e3)
    data['udp_send'].append((m_udf['ts'] - m_udf['ts_dec']).values * 1e3)
    data['total'].append((m_udf['ts'] - m_udf['ts_gen']).values * 1e3)
    labels.append(n_features)

fig, axes = plt.subplots(ncols=3, figsize=(4 * 3, 6), sharey=True)
for ikey, key in enumerate(['decoder', 'udp_send', 'total']):
    ax = axes[ikey]
    ax.violinplot(data[key], showmeans=True)
    ax.set_xticks(np.arange(len(data[key])) + 1)
    ax.set_xticklabels(labels)
    ax.set_xlabel('Number of Neural Channels')
    ax.set_ylabel('Latency (ms)')
    ax.set_title(key)
plt.tight_layout()
plt.subplots_adjust(top=0.90)
plt.suptitle(f'{decoder_type} decoder, {sample_rate} Hz data')
plt.savefig(f'latency_{decoder_type.lower()}_{sample_rate}Hz_auto_axis.pdf')

# %%
