#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ole_timing_test.py

import os
import sys
import time
import json
import redis
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

sys.path.append('..')

from timing_utils import log_hardware, plot_decoder_timing

# Connect to redis server
r = redis.Redis(host='localhost', port=6379)

test_time = 5
compare = False

# Define Graph
graph = {
    'metadata': {
        'participant_id': 0,
        'graph_name': 'ole_time_test',
        'description': 'Test timing for OLE from samples sent by the function generator'
    },
    'nodes': [
        {
            'name': 'func_generator',
            'version': 0.0,
            'nickname': 'func_generator',
            'stage': 'main',
            'module': '.',
            'redis_inputs': [],
            'redis_outputs': ['func_generator'],
            'run_priority': 99,
            'parameters': {
                'sample_rate': 200,
                'n_features': 256,
                'n_targets': 2,
                'log': 'INFO'
            }
        },
        {
            'name': 'decoder',
            'version': 0.0,
            'nickname': 'OLE',
            'stage': 'main',
            'module': '.',
            'redis_inputs': ['func_generator'],
            'redis_outputs': ['decoder'],
            'run_priority': 99,
            'parameters': {
                'n_features': 256,
                'n_targets': 2,
                'decoder_type': 'linear',
                'log': 'INFO',
                'loop': 'nanosleep'
            }
        }
    ]
}

# Start the graph
r.xadd('supervisor_ipstream', {
        'commands': 'startGraph',
        'graph': json.dumps(graph)
        }   
)

# Let graph run for test_time minutes (Default is 5)
print(f'Running OLE timing test graph for {test_time} min...')
total_secs = 60 * test_time

while total_secs:
    mins, secs = divmod(total_secs, 60)
    timer = ' Time remaining: {:02d}:{:02d}'.format(mins, secs)
    print(timer, end="\r")
    time.sleep(1)
    total_secs -= 1

print('Stopping graph...          ')

# Stop the Graph
r.xadd('supervisor_ipstream', {
        'commands': 'stopGraph'
        }   
)

# Plot total latencies between nodes
replies2 = r.xrange(b'decoder')
entries2 = []
for i, reply in enumerate(replies2):
    entry_id, entry_dict = reply
    entry = {
        'preds': np.frombuffer(entry_dict[b'y'], dtype=np.float32),
        'ts_in': float(entry_dict[b'ts_gen']),
        'ts_add': float(entry_dict[b'ts']),
        'ts_read': float(entry_dict[b'ts_read']),
        'i': int(entry_dict[b'i'])
    }
    entries2.append(entry)

ole_df = pd.DataFrame(entries2)
ole_df.set_index('i', inplace=True)

# Plot timing results
plot_decoder_timing(ole_df, 'OLE', test_time=test_time)

# Clear redis
r.delete('decoder')
r.delete('func_generator')
r.memory_purge()

# Save dataframe
if not os.path.exists('dataframes'):
    os.mkdir('dataframes/')

date_str = datetime.now().strftime(r'%m%d%y_%H%M')
with open(f'dataframes/{date_str}_ole.pkl', 'wb') as f:
    pickle.dump(ole_df, f)

# log hardware used
log_hardware(f'OLE_{date_str}')