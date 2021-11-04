# %%
import numpy as np
import pandas as pd
import yaml
from brand import initializeRedisFromYAML
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split

from utils import decode_field, get_lagged_features, smooth_data

# %%
# Connect to Redis
r = initializeRedisFromYAML('replayTest.yaml')

# %%
with open('stream_spec.yaml', 'r') as f:
    stream_spec = yaml.safe_load(f)

# %%
# Load data from Redis
# taskInput
all_entries = r.xread({b'taskInput': 0})
stream_entries = all_entries[0][1]
stream_data = [entry[1] for entry in stream_entries]

task_input = pd.DataFrame(stream_data)
for field in ['timestamps', 'samples']:
    task_input[field] = task_input[field.encode()].apply(
        decode_field, stream='taskInput', field=field, stream_spec=stream_spec)
task_input = task_input.set_index('timestamps')

# thresholdCrossings
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

# Separate channels into their own columns
tc_timestamps = threshold_crossings['timestamps'].values
crossings = np.stack(threshold_crossings['crossings'])
n_chans = crossings.shape[1]

channel_labels = [f'ch{i :03d}' for i in range(n_chans)]
tc_df = pd.DataFrame(crossings,
                     index=tc_timestamps + 13,
                     columns=channel_labels)

# %%
joined_df = task_input.join(tc_df, how='inner')
joined_df.index = pd.to_timedelta(joined_df.index / 30, unit='ms')
joined_df

# %%
samples = np.stack(joined_df['samples'])
joined_df['touch'] = samples[:, 0]
joined_df['x'] = samples[:, 1]
joined_df['y'] = samples[:, 2]

# %%
bin_size_ms = 5  # ms
gauss_width_ms = 20  # ms, for smoothing
binned_data = joined_df.resample(f'{bin_size_ms :d}ms').sum()

# %%
smoothed_data = smooth_data(binned_data[channel_labels].values,
                            bin_size=bin_size_ms,
                            gauss_width=gauss_width_ms)

X = get_lagged_features(smoothed_data, n_history=3)
y = binned_data[['x', 'y']].values

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

mdl = Ridge()
mdl.fit(X_train, y_train)

print(f'Train R^2: {mdl.score(X_train, y_train)}')
print(f'Test R^2: {mdl.score(X_test, y_test)}')

# %%
