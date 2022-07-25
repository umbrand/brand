#!/usr/bin/env python
# imports
import json
import subprocess

import redis
import numpy as np
import pandas as pd
import pickle
import matplotlib.pyplot as plt

from datetime import datetime

def scalarfrombuffer(*args, **kwargs):
    return np.frombuffer(*args, **kwargs)[0]


def stream_to_df(stream_entries, fields, dtypes):
    data = [None] * len(stream_entries)
    for i, (_, entry_data) in enumerate(stream_entries):
        data[i] = {f: entry_data[f.encode()] for f in fields}

    df = pd.DataFrame(data)
    for f, dtype in zip(fields, dtypes):
        df[f] = df[f].apply(scalarfrombuffer, dtype=dtype)
    return df

# get cpu info
command = "lscpu | grep 'Model name' | cut -f 2 -d \":\""
cpu_model = subprocess.check_output(command, shell=True).strip().decode()
cpu_model
print(f'Running tests on CPU model: {cpu_model}')

# Connect to Redis
r = redis.Redis()

# Define the default graph
default_graph = {
    'metadata': {
        'participant_id': 0,
        'graph_name': 'pubSubTest',
        'description': 'Test pub-sub communication'
    },
    'nodes': [
        {
            'name': 'subscriber',
            'version': 0.0,
            'nickname': 'subscriber',
            'stage': 'main',
            'module': '.',
            'redis_inputs': ['publisher'],
            'redis_outputs': ['subscriber'],
            'run_priority': 99,
            'parameters': {
                'log': 'INFO',
                'in_stream': 'publisher',
                'write_data': False
            }
        },
        {
            'name': 'publisher',
            'version': 0.0,
            'nickname': 'publisher',
            'stage': 'main',
            'module': '.',
            'redis_inputs': [],
            'redis_outputs': ['publisher'],
            'run_priority': 99,
            'parameters': {
                'log': 'INFO',
                'n_channels': 128,
                'seq_len': 30,
                'data_type': 'int16',
                'duration': 300,
                'sample_rate': 1000,
                'stop_graph_when_done': True
            }
        },
    ]
}

# configure the graph
pub_idx = 1
sub_idx = 0

graph = default_graph.copy()
pub_params = graph['nodes'][pub_idx]['parameters']
sub_params = graph['nodes'][sub_idx]['parameters']

# store the number of channels
n_channels = pub_params['n_channels']
pub_params['n_channels'] = n_channels
# set parameters
graph['nodes'][pub_idx]['parameters'] = pub_params
graph['nodes'][sub_idx]['parameters'] = sub_params

# start graph
last_id = r.xadd('supervisor_ipstream', {
    'commands': 'startGraph',
    'graph': json.dumps(graph)
})

# wait for the graph to stop
done = False
while not done:
    streams = r.xread({'supervisor_ipstream': last_id}, block=0)
    key, messages = streams[0]
    last_id, data = messages[0]
    cmd = (data[b'commands']).decode("utf-8")
    if cmd == "stopGraph":
        done = True

# load stream data into a dataframe
pub_entries = r.xrange('publisher')
pub_df = stream_to_df(pub_entries, ['i', 't'], ['uint64', 'uint64'])
pub_df = pub_df.set_index('i', drop=False)

sub_entries = r.xrange('subscriber')
sub_df = stream_to_df(sub_entries, ['i', 't'], ['uint64', 'uint64'])
sub_df = sub_df.set_index('i', drop=False)

pubsub_df = sub_df.join(pub_df, lsuffix='_sub', rsuffix='_pub')

# set num channels
pubsub_df['n_channels'] = n_channels

#Calculate Latencies and sample intervals
latencies = (pubsub_df['t_sub'] - pubsub_df['t_pub']).values / 1e6
pub_intervals = np.diff(pubsub_df['t_pub'].values) / 1e6

# analyze timing
print(f'n_channels = {n_channels}, latency: {latencies.mean() } '
    f'+- {latencies.std()} ({latencies.min()} - {latencies.max()}) ms')

#Plot timing information
fig, axs = plt.subplots(4, 1, figsize=(17,14))
thres = (1 / pub_params['sample_rate']) * 1000
plt.tight_layout()
plt.subplots_adjust(hspace=0.3)

# Subplot 1
dur_int = np.arange(pub_intervals.shape[0]) / pub_params['sample_rate']
axs[0].plot(dur_int, pub_intervals, label=f'Mean: {pub_intervals.mean()}')
axs[0].axhline(thres, color='red', linestyle='dashed', label=f'Sample Interval Threshold: {thres} ms')
axs[0].set_title('Sample Intervals vs Time in Publisher')
axs[0].set_xlabel('Test Duration (s)')
axs[0].set_ylabel('Sample Interval (ms)')
axs[0].legend(loc='upper left')

# Subplot 2
step_int = 0.5
bins = np.arange(np.ceil(pub_intervals.max()) + step_int, step=step_int)
axs[1].hist(pub_intervals, bins=bins, histtype='step', linewidth=2)
axs[1].set_title('Sample Frequency in Publisher')
axs[1].set_xlabel('Latency (ms)')
axs[1].set_ylabel('Samples')
axs[1].set_yscale('log')

# Subplot 3
dur_lat = np.arange(latencies.shape[0]) / pub_params['sample_rate']
axs[2].plot(dur_lat, latencies, label=f'Mean: {latencies.mean()}')
axs[2].axhline(thres, color='red', linestyle='dashed', label=f'Latency Threshold: {thres} ms')
axs[2].set_title('Latency vs Time (Pub -> Sub)')
axs[2].set_xlabel('Test Duration (s)')
axs[2].set_ylabel('Latency (ms)')
axs[2].legend(loc='upper left')

# Subplot 4
step_lat = 0.05
bins = np.arange(np.ceil(latencies.max()) + step_lat, step=step_lat)
axs[3].hist(latencies, bins=bins, histtype='step', linewidth=3)
axs[3].set_title('Latency Frequency (Pub -> Sub)')
axs[3].axvline(thres, color='red', linestyle='dashed', label=f'Latency Threshold: {thres} ms')
axs[3].set_xlabel('Latency (ms)')
axs[3].set_ylabel('Samples')
axs[3].set_yscale('log')
axs[3].legend(loc='upper center')

date_str = datetime.now().strftime(r'%y%m%dT%H%M')
fig.savefig(f'plots/{date_str}_pubsub_timing.png', facecolor='white', transparent=False)

# delete publisher and subscriber streams
r.delete('publisher')
r.delete('subscriber')
r.memory_purge()

#save df
with open(f'dataframes/{date_str}_pubsub_data.pkl', 'wb') as f:
    pickle.dump(pubsub_df, f)
