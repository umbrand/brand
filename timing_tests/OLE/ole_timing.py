#!/usr/bin/env python

import redis
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pickle
import json
import time

from datetime import datetime

# Connect to redis server
r = redis.Redis(host='localhost', port=6379)

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
            #'run_priority': 99,
            'parameters': {
                'sample_rate': 200,
                'n_features': 130,
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
            #'run_priority': 99,
            'parameters': {
                'n_features': 130,
                'n_targets': 2,
                'decoder_type': 'linear',
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

# Let graph run for 5 minutes
timer = time.time()
last_min = 10
print('Starting Timer...')
while int(time.time() - timer) < 300:
    current_time = int(time.time() - timer)
    min = current_time // 60
    if min != last_min:
        print(f'Minutes Passed: {min}')
        last_min = min

# Stop the Graph
print('Stopping graph...')
r.xadd('supervisor_ipstream', {
        'commands': 'stopGraph'
        }   
)

#Create Dataframe from streams
replies1 = r.xrange(b'func_generator')

entries1 = []
for i, reply in enumerate(replies1):
    entry_id, entry_dict = reply
    entry = {
        'samples': np.frombuffer(entry_dict[b'samples'], dtype=np.float64),
        'ts': float(entry_dict[b'ts']),
        'sync': entry_dict[b'sync'],
        'i': int(entry_dict[b'i'])
    }
    entries1.append(entry)

func_gen_df = pd.DataFrame(entries1)
func_gen_df.set_index('i', inplace=True)

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

ole_data = pd.DataFrame(entries2)
ole_data.set_index('i', inplace=True)

#clear redis
r.delete('func_generator')
r.delete('decoder')
r.memory_purge()

# save dataframe
date_str = datetime.now().strftime(r'%y%m%dT%H%M')
with open(f'dataframes/{date_str}_data.pkl', 'wb') as f:
    pickle.dump(func_gen_df, f)
    pickle.dump(ole_data, f)