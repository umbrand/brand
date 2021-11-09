#!/usr/bin/env python

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from brand import get_node_parameter_value, initializeRedisFromYAML
import seaborn as sns


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

# %%
# Get run info
sample_rate = get_node_parameter_value(YAML_FILE, 'func_generator',
                                       'sample_rate')
n_features = get_node_parameter_value(YAML_FILE, 'func_generator',
                                      'n_features')
n_targets = get_node_parameter_value(YAML_FILE, 'func_generator', 'n_targets')
decoder_type = get_node_parameter_value(YAML_FILE, 'decoder', 'decoder_type')

# %%
data = np.array([
    udf['ts_dec'] - udf['ts_gen'],  # decoder latency
    udf['ts'] - udf['ts_dec'],  # udp sender latency
    udf['ts'] - udf['ts_gen']  # total latency
])
# %%
# %%
data = np.array([
    udf['ts_dec'] - udf['ts_gen'],  # decoder latency
    udf['ts'] - udf['ts_dec'],  # udp sender latency
    udf['ts'] - udf['ts_gen']  # total latency
])
xdata = (['Decoder'] * data.shape[1] + ['UDP Sender'] * data.shape[1] +
         ['Total'] * data.shape[1])

# %%
sns.stripplot(y=data.ravel() * 1e3, x=xdata, alpha=0.25)
sns.violinplot(y=data.ravel() * 1e3, x=xdata)
plt.savefig('stripplot_example.png')
# %%
