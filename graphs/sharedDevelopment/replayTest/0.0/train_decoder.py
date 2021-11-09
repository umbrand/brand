# %%
import joblib
import numpy as np
import pandas as pd
import yaml
from brand import initializeRedisFromYAML
from numpy.lib.npyio import save
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import train_test_split

from utils import get_lagged_features, load_stream
import pickle

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

X = get_lagged_features(neural_data, n_history=50)
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
with open('model.pkl', 'wb') as f:
    pickle.dump(mdl, f)
# %%
