# %%
import os

import joblib
import numpy as np
import pandas as pd
import yaml
from brand import initializeRedisFromYAML
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import train_test_split
from tensorflow import keras

from utils import get_lagged_features, load_stream

# %%
# Connect to Redis
r = initializeRedisFromYAML('replayTest.yaml')

# %%
with open('stream_spec.yaml', 'r') as f:
    stream_spec = yaml.safe_load(f)

# %%
# Load data from Redis
# taskInput
task_input = load_stream(r, 'taskInput', stream_spec=stream_spec)
task_input = task_input.set_index('timestamps')

# thresholdCrossings
threshold_crossings = load_stream(r,
                                  'thresholdCrossings',
                                  stream_spec=stream_spec)

# Separate channels into their own columns
tc_timestamps = threshold_crossings['timestamps'].values
crossings = np.stack(threshold_crossings['crossings'])
n_chans = crossings.shape[1]

# %%
# offset correction
offsets = list(range(-15, 16))
idx = np.argmax([
    np.intersect1d(task_input.index, tc_timestamps + i).shape[0]
    for i in offsets
])
offset = offsets[idx]
offset

# %%
channel_labels = [f'ch{i :03d}' for i in range(n_chans)]
tc_df = pd.DataFrame(crossings,
                     index=tc_timestamps + offset,
                     columns=channel_labels)

# %%
joined_df = task_input.join(tc_df, how='inner')
joined_df.index = pd.to_timedelta(joined_df.index / 30, unit='ms')
joined_df

# %%
# split the behavioral data into columns
samples = np.stack(joined_df['samples'])
joined_df['touch'] = samples[:, 0]
joined_df['x'] = samples[:, 1]
joined_df['y'] = samples[:, 2]

# %%
bin_size_ms = 5  # ms
binned_data = joined_df.resample(f'{bin_size_ms :d}ms').mean().dropna(axis=0)

# %%
# Decoding
neural_data = binned_data[channel_labels].values

X = get_lagged_features(neural_data, n_history=15)
y = binned_data[['x', 'y']].values

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

with joblib.parallel_backend('loky'):
    mdl = RidgeCV(alphas=np.logspace(-1, 3, 20))
mdl.fit(X_train, y_train)

print(f'Best L2: {mdl.alpha_}')
print(f'Train R^2: {mdl.score(X_train, y_train)}')
print(f'Test R^2: {mdl.score(X_test, y_test)}')

y_pred = mdl.predict(X)
binned_data['x_pred'] = y_pred[:, 0]
binned_data['y_pred'] = y_pred[:, 1]

# %%
# Save the model
keras.models.load_model(os.getcwd())

# %%
# Split the data into trials
# state: [start_trial, movement, reward, failure, between_trials]
state = load_stream(r, 'state', stream_spec=stream_spec)
state.sort_values('sync', inplace=True)
# Assign trial numbers
state['trial_id'] = None  # make a new column

# number the 'start_trial' tokens
mask = state['state'] == 'start_trial'
state.loc[mask, 'trial_id'] = np.arange(len(state[mask]))

# assign the 'start_trial' number to tokens that come after it
current_trial = None
trial_ids = np.empty_like(state['trial_id'])
for i in range(state.shape[0]):
    if state['trial_id'].iloc[i] is not None:
        current_trial = state['trial_id'].iloc[i]
    trial_ids[i] = current_trial
state['trial_id'] = trial_ids

# %%
trials = state.pivot(index='trial_id', columns='state', values='sync')
trials.sort_index(axis=1, inplace=True)  # sort columns after pivoting
# drop failed trials and the between-trial period
trials.drop(['between_trials', 'failure'], axis=1, inplace=True)
trials.dropna(axis=0, inplace=True)  # drop incomplete trials
trials = trials / 30  # convert to milliseconds
for field in trials.columns:
    trials[field] = pd.to_timedelta(trials[field], unit='ms')
trials

# %%
trial_dfs = []
align_field = 'movement'
start_offset, end_offset = pd.to_timedelta((-500, 1000), unit='ms')
bin_width = pd.to_timedelta(bin_size_ms, unit='ms')
for tid in trials.index.values:
    center = trials[align_field].loc[tid]
    a = center + start_offset
    b = center + end_offset
    trial_df = binned_data.loc[a:b].copy()
    trial_df['trial_id'] = tid
    trial_df['align_time'] = trial_df.index.ceil(bin_width) - center.ceil(
        bin_width)
    trial_dfs.append(trial_df)

# Combine all trials into one DataFrame
trial_data = pd.concat(trial_dfs, ignore_index=True)
aligned_trials = trial_data.pivot_table(index='align_time', columns='trial_id')

# %%
# plot predictions
import matplotlib.pyplot as plt

trial_ids = trial_data['trial_id'].unique()[:10]

fig, axes = plt.subplots(ncols=2,
                         nrows=len(trial_ids),
                         figsize=(8, 2 * len(trial_ids)))

for i, trial_id in enumerate(trial_ids):
    t = aligned_trials.index.total_seconds()
    axes[i, 0].plot(t, aligned_trials['x'][trial_id], label='true')
    axes[i, 0].plot(t,
                    aligned_trials['x_pred'][trial_id],
                    label='predicted',
                    alpha=0.7)
    axes[i, 0].set_xlabel(f'Time from \n{align_field} (s)')
    axes[i, 0].set_ylabel(f'Trial {trial_id}')
    axes[i, 1].plot(t, aligned_trials['y'][trial_id], label='true')
    axes[i, 1].plot(t,
                    aligned_trials['y_pred'][trial_id],
                    label='predicted',
                    alpha=0.7)
    axes[i, 1].set_xlabel(f'Time from \n{align_field} (s)')
axes[0, 0].set_title('x')
axes[0, 1].set_title('y')
axes[0, -1].legend()

plt.tight_layout()
plt.savefig('force_predictions.pdf')
# %%
