#!/usr/bin/env python

# %%
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
from brand import get_node_parameter_value, initializeRedisFromYAML

try:
    plt.close(plt.figure())
except Exception:
    plt.switch_backend('Agg')

YAML_FILE = 'replayTest.yaml'
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
date_str = datetime.now().strftime(r'%y%m%dT%H%M')
udf.to_csv(f'{date_str}_timestamps_{sample_rate}Hz.csv')

# %%
