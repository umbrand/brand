# %%
import numpy as np
import h5py
import os
import matplotlib.pyplot as plt
import pandas as pd
from glob import glob
from tqdm.auto import tqdm

# %%
log_files = sorted(glob('labgraph_team_data/*'))
latency_summaries = []
for log_file in log_files:
    # load data
    this_dir = os.path.dirname(__file__)
    h5_file = os.path.join(this_dir, log_file)
    with h5py.File(h5_file, 'r') as h5f:
        block_sizes = sorted([
            int(key.split('_')[2]) for key in h5f.keys()
            if key.startswith('sample_summary')
        ])

        # create a list of dictionaries with summary stats on latencies
        latency_summary = [None] * len(block_sizes)
        for i_block, bs in enumerate(tqdm(block_sizes)):
            block_data = {'block_size': bs}

            # compute latencies
            summary = h5f[f"sample_summary_{bs :d}"]
            send_latencies = np.diff(summary['sent_timestamp']) * 1e3  # ms
            rec_latencies = np.diff(summary['received_timestamp']) * 1e3  # ms
            send_rec_latencies = (summary['received_timestamp'] -
                                  summary['sent_timestamp']) * 1e3  # ms

            # compute summary statistics
            for ldata, field in [[send_latencies, 'send_latency'],
                                 [rec_latencies, 'receive_latency'],
                                 [send_rec_latencies, 'send_receive_latency']]:
                block_data[f'{field}_mean'] = np.mean(ldata)
                block_data[f'{field}_std'] = np.std(ldata)
                block_data[f'{field}_min'] = np.min(ldata)
                block_data[f'{field}_max'] = np.max(ldata)

            # add language and platform information from the filename
            block_data['language'], block_data['platform'] = (
                os.path.basename(log_file).split('.')[0].split('_')[-2:])

            latency_summary[i_block] = block_data
    latency_summaries += latency_summary

# %%
latency_df = pd.DataFrame(latency_summaries)
latency_df.to_csv('labgraph_latencies_lg_team.csv')
# %%
