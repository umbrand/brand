# %%
import os
import pickle

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from brand import initializeRedisFromYAML
from tensorflow import keras

from utils import find_offset, get_lagged_features, load_stream

# %%
# Options
N_HISTORY = 15

# %%
# Connect to Redis
r = initializeRedisFromYAML('replayTest.yaml')

# Load stream information
with open('stream_spec.yaml', 'r') as f:
    stream_spec = yaml.safe_load(f)

# %%
# Load decoder output
decoder_out = load_stream(r, 'decoder', stream_spec=stream_spec)

# create timedelta index
decoder_out['idx'] = pd.to_timedelta(decoder_out['timestamps'].values / 30,
                                     unit='ms')
decoder_out.set_index('idx', inplace=True)
decoder_out.sort_index(inplace=True)
# split the predictions into columns
samples = np.stack(decoder_out['samples'])
decoder_out['touch_d'] = samples[:, 0]
decoder_out['x_d'] = samples[:, 1]
decoder_out['y_d'] = samples[:, 2]
# save the prediction timestamps to a uniquely named column
decoder_out['ts_d'] = decoder_out['ts'].values

# %%
# Load thresholdCrossings
threshold_crossings = load_stream(r, 'tc_replay', stream_spec=stream_spec)

# Separate channels into their own columns
crossings = np.stack(threshold_crossings['crossings'])
channel_labels = [f'ch{i :03d}' for i in range(crossings.shape[1])]
tc_df = pd.DataFrame(crossings,
                     index=threshold_crossings['timestamps'],
                     columns=channel_labels)
tc_df['ts_tc'] = threshold_crossings['ts'].values

# drop samples that precede the decoder output to avoid an offset when binning
mask = tc_df.index < decoder_out['timestamps'].min()
tc_df.drop(tc_df.index[mask], axis=0, inplace=True)

# %%
# Load taskInput
task_input = load_stream(r, 'taskInput', stream_spec=stream_spec)

# offset correction
ti_timestamps = task_input['timestamps'].values
offset = find_offset(tc_df.index.values, ti_timestamps)
task_input['timestamps'] = ti_timestamps + offset
task_input.set_index('timestamps', inplace=True)

# split the behavioral data into columns
samples = np.stack(task_input['samples'])
task_input['touch'] = samples[:, 0]
task_input['x'] = samples[:, 1]
task_input['y'] = samples[:, 2]

joined_df = task_input.join(tc_df, how='inner')
# convert from a samples index to a timedelta index
joined_df['sync'] = joined_df.index.values
joined_df.index = pd.to_timedelta(joined_df.index / 30, unit='ms')
joined_df

# %%
# bin the data
bin_size_ms = 5  # ms
binned_data = joined_df.resample(f'{bin_size_ms :d}ms').mean()
binned_data['sync'] = joined_df['sync'].resample(f'{bin_size_ms :d}ms').min()
binned_data['ts_tc'] = joined_df['ts_tc'].resample(f'{bin_size_ms :d}ms').max()
# merge the decoder output with the binned data
binned_data = binned_data.join(decoder_out)
binned_data.dropna(axis=0, inplace=True)
# %%
# Offline decoder predictions
mdl = keras.models.load_model(os.getcwd())
scaler_path = './scaler.pkl'
scaler = pickle.load(open(scaler_path, 'rb'))

X = get_lagged_features(binned_data[channel_labels].values,
                        n_history=N_HISTORY)
y = mdl.predict(X)
y = scaler.inverse_transform(y)

binned_data['x_offline'] = y[:, 0]
binned_data['y_offline'] = y[:, 1]
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

trials = state.pivot(index='trial_id', columns='state', values='sync')
trials.sort_index(axis=1, inplace=True)  # sort columns after pivoting
# drop failed trials and the between-trial period
trials.drop(['between_trials', 'failure'], axis=1, inplace=True)
trials.dropna(axis=0, inplace=True)  # drop incomplete trials
trials = trials / 30  # convert to milliseconds
for field in trials.columns:
    trials[field] = pd.to_timedelta(trials[field], unit='ms')

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
trial_ids = trial_data['trial_id'].unique()[:10]

fig, axes = plt.subplots(ncols=2,
                         nrows=len(trial_ids),
                         figsize=(8, 2 * len(trial_ids)))

for i, trial_id in enumerate(trial_ids):
    t = aligned_trials.index.total_seconds()
    axes[i, 0].plot(t, aligned_trials['x'][trial_id], label='true')
    axes[i, 0].plot(t,
                    aligned_trials['x_d'][trial_id],
                    '--',
                    label='online',
                    alpha=0.7)
    axes[i, 0].plot(t,
                    aligned_trials['x_offline'][trial_id],
                    '-.',
                    label='offline',
                    alpha=0.7)
    axes[i, 0].set_xlabel(f'Time from \n{align_field} (s)')
    axes[i, 0].set_ylabel(f'Trial {trial_id}')
    axes[i, 1].plot(t, aligned_trials['y'][trial_id], label='true')
    axes[i, 1].plot(t,
                    aligned_trials['y_d'][trial_id],
                    '--',
                    label='online',
                    alpha=0.7)
    axes[i, 1].plot(t,
                    aligned_trials['y_offline'][trial_id],
                    '-.',
                    label='offline',
                    alpha=0.7)
    axes[i, 1].set_xlabel(f'Time from \n{align_field} (s)')
axes[0, 0].set_title('x')
axes[0, 1].set_title('y')
axes[0, -1].legend()

plt.tight_layout()
plt.savefig('ffn_force_predictions_online.pdf')

# %%
matplotlib.rcParams.update({'font.size': 20})

# Analyze timing
# get the difference between the
data = (
    # decoder timestamps
    binned_data['ts_d']
    # timestamp of the last sample in the bin at the decoder input
    - binned_data['ts_tc']).values * 1e3

dataset = [data]
xticks = [1]
xlabels = ['Feedforward\nNeural Network']

upper_outliers = [dat[dat > dat.mean() + 3 * dat.std()] for dat in dataset]

plt.figure(figsize=(3 * len(dataset), 6))
plt.violinplot(dataset, showextrema=False, showmedians=True)
for i in range(len(dataset)):
    plt.plot(np.ones_like(upper_outliers[i]) + i,
             upper_outliers[i],
             'o',
             color='C0',
             fillstyle='none')
plt.ylim([0, None])
plt.xticks(ticks=xticks, labels=xlabels)
plt.tight_layout()
plt.ylabel('Latency (ms)')
plt.savefig('ffn_decoder_latency.pdf')

# %%
binned_data.to_csv('ffn_binned_data.csv')
aligned_trials.to_csv('ffn_aligned_trials.csv')

# %%
