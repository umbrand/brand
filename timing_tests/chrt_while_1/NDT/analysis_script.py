#!/usr/bin/env python
from turtle import position
import redis
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pickle
import json
import time
from tqdm.autonotebook import tqdm
from datetime import datetime

import sys
sys.path.append('..')
  
from timing_utils import plot_decoder_timing, log_hardware

test_time=5
compare=True

# Connect to redis server
r = redis.Redis(host='localhost', port=6379)

# Define Graph
graph = {
    
    'metadata': {
        'participant_id': 0,
        'graph_name': 'ndt_lantency_analysis',
        'description': 'ndt decoder latency analysis'
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
            # 'run_priority': 99,
            'parameters': {
                'sample_rate': 200,
                'n_features': 142,
                'n_targets': 2,
                'log': 'INFO'
            }
        },
        {
            'name': 'ndt',
            'version': 0.0,
            'nickname': 'ndt',
            'stage': 'main',
            'module': '.',
            'redis_inputs': ['func_generator'],
            'redis_outputs': ['ndt'],
            # 'run_priority': 99,
            'parameters': {
                'n_features': 142,
                'cfg_path': 'nodes/ndt/src/config.yaml',
                'input_stream': 'func_generator',
                'input_field': 'samples',
                'input_dtype': 'float64',
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
print(f'Running graph for {test_time} min...')
total_secs = 5 * test_time

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

#Create Dataframe from streams
replies1 = r.xrange(b'ndt')

entries1 = []
for i, reply in enumerate(replies1):
    entry_id, entry_dict = reply
    entry = {
        'ts_before': float(entry_dict[b'ts_before']),
        'ts_after': float(entry_dict[b'ts_after']),
        'ts_read': float(entry_dict[b'ts_read']),
        'ts_add': float(entry_dict[b'ts_add']),
        'ts_in': float(entry_dict[b'ts_in']),
        'i': entry_dict[b'i'],
        'i_in': entry_dict[b'i_in']
    }
    entries1.append(entry)

ndt_df = pd.DataFrame(entries1)
ndt_df.set_index('i', inplace=True)

# Plot time intervals between samples (func_generator)
plot_decoder_timing(ndt_df, 'NDT', test_time=test_time)

#clear redis
r.delete('ndt')
r.delete('func_generator')
r.memory_purge()

# # save dataframe
date_str = datetime.now().strftime(r'%m%d%y_%H%M')
with open(f'dataframes/{date_str}_ndt.pkl', 'wb') as f:
    pickle.dump(ndt_df, f)

log_hardware(f'NDT_{date_str}')
            