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
YAML_FILE = 'replayTest.yaml'

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
n_feature_list = udf['n_features'].unique()
for n_features in n_feature_list:
    mask = udf['n_features'] == n_features
    m_udf = udf[mask]
    data['decoder'].append((m_udf['ts_dec'] - m_udf['ts_gen']).values * 1e3)
    data['udp_send'].append((m_udf['ts'] - m_udf['ts_dec']).values * 1e3)
    data['total'].append((m_udf['ts'] - m_udf['ts_gen']).values * 1e3)
    labels.append(n_features)

plt.rc('font', size=20) 
fig, axes = plt.subplots(ncols=3, figsize=(4 * 3, 6), sharey=True)
for ikey, key in enumerate(['decoder', 'udp_send', 'total']):
    ax = axes[ikey]
    ax.violinplot(data[key], showmeans=True)
    ax.set_xticks(np.arange(len(data[key])) + 1)
    ax.set_xticklabels(labels)
    ax.set_xlabel('Number of\nNeural Channels')
    ax.set_title(key)
axes[0].set_ylabel('Latency (ms)')
plt.tight_layout()
# plt.subplots_adjust(top=0.8)
# plt.suptitle(f'{decoder_type} decoder, {sample_rate} Hz data')
plt.savefig(f'latency_{decoder_type.lower()}_{sample_rate}Hz.pdf')

# %%
n_features = 256
mask = udf['n_features'] == n_features
m_udf = udf[mask]
n_targets = m_udf['n_targets'].iloc[0]

fig, ax = plt.subplots(figsize=(6, 6))
data = np.array([
    m_udf['ts_dec'] - m_udf['ts_gen'],  # decoder latency
    m_udf['ts'] - m_udf['ts_dec'],  # udp sender latency
    m_udf['ts'] - m_udf['ts_gen']  # total latency
])
ax.violinplot(data.T * 1e3, showmeans=True)
ax.set_xticks(np.arange(data.shape[0]) + 1)
ax.set_xticklabels(['Decoder', 'UDP Sender', 'Total'])
ax.set_ylabel('Latency (ms)')
ax.set_title(f'{decoder_type} decoder, {sample_rate} Hz data\n'
             f'{n_features} neural ch, {n_targets} kinematic ch')
plt.tight_layout()
plt.savefig(f'latency_{decoder_type.lower()}_{sample_rate}Hz'
            f'_{n_features}n_{n_targets}k.pdf')

# %%
