# %%
import numpy as np
import pandas as pd
import yaml
from brand import initializeRedisFromYAML

from utils import decode_field

# %%
# Connect to Redis
r = initializeRedisFromYAML('replayTest.yaml')

# %%
with open('stream_spec.yaml', 'r') as f:
    stream_spec = yaml.safe_load(f)

# %%
all_entries = r.xread({b'thresholdCrossings': 0})
stream_entries = all_entries[0][1]
stream_data = [entry[1] for entry in stream_entries]

threshold_crossings = pd.DataFrame(stream_data)
for field in ['timestamps', 'crossings']:
    threshold_crossings[field] = threshold_crossings[field.encode()].apply(
        decode_field,
        stream='thresholdCrossings',
        field=field,
        stream_spec=stream_spec)

# %%
all_entries = r.xread({b'taskInput': 0})
stream_entries = all_entries[0][1]
stream_data = [entry[1] for entry in stream_entries]

task_input = pd.DataFrame(stream_data)
for field in ['timestamps', 'samples']:
    task_input[field] = task_input[field.encode()].apply(
        decode_field,
        stream='taskInput',
        field=field,
        stream_spec=stream_spec)
task_input = task_input.set_index('timestamps')

# %%
tc_timestamps = threshold_crossings['timestamps'].values
crossings = np.stack(threshold_crossings['crossings'])
n_chans = crossings.shape[1]

channel_labels = [f'ch{i :03d}' for i in range(n_chans)]
df = pd.DataFrame(crossings,
                  index=tc_timestamps + 13,
                  columns=channel_labels)

# %%
joined_df = task_input.join(df, how='inner')
joined_df.index = pd.to_timedelta(joined_df.index / 30, unit='ms')
joined_df
# %%
samples = np.stack(joined_df['samples'])
joined_df['touch'] = samples[:, 0]
joined_df['x'] = samples[:, 1]
joined_df['y'] = samples[:, 2]

# %%
binned_data = joined_df.resample('5ms').sum()

# %%
