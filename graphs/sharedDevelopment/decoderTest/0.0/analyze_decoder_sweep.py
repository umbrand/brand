#!/usr/bin/env python

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from redis import Redis

try:
    plt.close(plt.figure())
except Exception:
    plt.switch_backend('Agg')

# %%
# Get run info
YAML_FILE = 'func_generator.yaml'


def get_parameter_value(fileName, field):
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


sample_rate = get_parameter_value('func_generator.yaml', 'sample_rate')
n_features = get_parameter_value('func_generator.yaml', 'n_features')
n_targets = get_parameter_value('func_generator.yaml', 'n_targets')
decoder_type = get_parameter_value('decoder.yaml', 'decoder_type')

# %%
# Load entries from udp_send
redis_ip = "127.0.0.1"
redis_port = 6379

entry_id = b'0-0'
entries = []
r = Redis(host=redis_ip, port=redis_port)
replies = r.xrange(b'udp_send')
r.close()

# %%
for reply in replies:
    entry_id, entry_dict = reply
    entries.append(entry_dict)

udf = pd.DataFrame(entries)
udf.rename(columns={col: col.decode() for col in udf.columns}, inplace=True)
udf['ts_gen'] = udf['ts_gen'].astype(float)
udf['ts_dec'] = udf['ts_dec'].astype(float)
udf['ts'] = udf['ts'].astype(float)
udf['n_features'] = udf['n_features'].astype(float).astype(int)
udf['n_targets'] = udf['n_targets'].astype(float).astype(int)

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
fig, axes = plt.subplots(ncols=3, figsize=(4 * 3, 8), sharey=True)
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
plt.suptitle(f'{decoder_type} decoder, {sample_rate} Hz data, '
             f'{n_targets} kinematic ch')
plt.savefig(f'latency_{decoder_type.lower()}_{sample_rate}Hz'
            f'_{n_targets}k.pdf')

# %%
