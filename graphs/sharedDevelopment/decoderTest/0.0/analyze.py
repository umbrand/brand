#!/usr/bin/env python

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from brand import get_node_parameter_value, initializeRedisFromYAML

try:
    plt.close(plt.figure())
except Exception:
    plt.switch_backend('Agg')

YAML_FILE = 'decoderTest.yaml'
# %%
# Load entries from udp_send
entry_id = b'0-0'
entries = []
r = initializeRedisFromYAML(YAML_FILE)
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
# Get run info
sample_rate = get_node_parameter_value(YAML_FILE, 'func_generator',
                                       'sample_rate')
n_features = get_node_parameter_value(YAML_FILE, 'func_generator',
                                      'n_features')
n_targets = get_node_parameter_value(YAML_FILE, 'func_generator', 'n_targets')
decoder_type = get_node_parameter_value(YAML_FILE, 'decoder', 'decoder_type')

# %%
# Save results
udf.to_csv(f'timestamps_{n_features :03d}ch.csv')

# %%
fig, ax = plt.subplots(figsize=(6, 4))
data = np.array([
    udf['ts_dec'] - udf['ts_gen'],  # decoder latency
    udf['ts'] - udf['ts_dec'],  # udp sender latency
    udf['ts'] - udf['ts_gen']  # total latency
])
ax.violinplot(data.T * 1e3, showmeans=True)
ax.set_xticks(np.arange(data.shape[0]) + 1)
ax.set_xticklabels(['Decoder', 'UDP Sender', 'Total'])
ax.set_ylabel('Latency (ms)')
ax.set_title(f'{decoder_type} decoder, {sample_rate} Hz data\n'
             f'{n_features} neural ch, {n_targets} kinematic ch')

plt.savefig(f'latency_{decoder_type.lower()}_{sample_rate}Hz'
            f'_{n_features}n_{n_targets}k.pdf')


# %%
