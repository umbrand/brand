#!/usr/bin/env python

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from redis import Redis
import yaml

try:
    plt.close(plt.figure())
except Exception:
    plt.switch_backend('Agg')
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
