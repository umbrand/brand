#!/usr/bin/env python
# -*- coding: utf-8 -*-
# rnn_timing_test.py

import os
import sys
import json
import time
import redis
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

sys.path.append('..')

from timing_utils import log_hardware, plot_decoder_timing

test_time = 5
compare = False

# Connect to redis server
r = redis.Redis(host='localhost', port=6379)

# Define Graph
graph = {
    'metadata': {
        'participant_id': 0,
        'graph_name': 'RNN_timing_test',
        'description': 'Test timing for RNN from samples sent by the function generator using nanosleep loop'
    },
    'nodes': [
        {
            'name': 'func_generator_sleep',
            'version': 0.0,
            'nickname': 'func_generator_sleep',
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
            'name': 'RNN_decoder',
            'version': 0.0,
            'nickname': 'RNN',
            'stage': 'main',
            'module': '.',
            'redis_inputs': ['func_generator'],
            'redis_outputs': ['rnn_decoder'],
            'run_priority': 99,
            'parameters': {
                'n_features': 256,
                'n_targets': 2,
                'seq_len': 30,
                'model_pth': './nodes/RNN_decoder/src/train_RNN.yaml',
                'log': 'INFO'
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
print(f'Running RNN timing test graph for {test_time} min...')
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
replies2 = r.xrange(b'rnn_decoder')
entries2 = []
for i, reply in enumerate(replies2):
    entry_id, entry_dict = reply
    entry = {
        'preds': np.frombuffer(entry_dict[b'y'], dtype=np.float32),
        'ts_in': float(entry_dict[b'ts_gen']),
        'ts_add': float(entry_dict[b'ts']),
        'ts_read': float(entry_dict[b'read_time']),
        'before_pred': float(entry_dict[b'before_pred']),
        'i': int(entry_dict[b'i'])
    }
    entries2.append(entry)

rnn_df = pd.DataFrame(entries2)
rnn_df.set_index('i', inplace=True)

# Plot timing results
plot_decoder_timing(rnn_df, 'RNN', test_time=test_time)

# Clear redis
r.delete('rnn_decoder')
r.delete('func_generator')
r.memory_purge()

# Save dataframe
if not os.path.exists('dataframes'):
    os.mkdir('dataframes/')

date_str = datetime.now().strftime(r'%m%d%y_%H%M')
with open(f'dataframes/{date_str}_rnn.pkl', 'wb') as f:
    pickle.dump(rnn_df, f)

# log hardware used
log_hardware(f'RNN_{date_str}')