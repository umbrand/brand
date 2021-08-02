# %%
import os
import h5py
import numpy as np
import matplotlib.pyplot as plt

LG_LOG = 'MnoSJ0WH71PJKjBk.h5'

this_dir = os.path.dirname(__file__)
h5_file = os.path.join(this_dir, LG_LOG)
# %%
h5f = h5py.File(h5_file, 'r')

# %%
data = h5f['noise_avg'].value
real_sample_interval = np.diff(data['timestamp'])

# %%
np.mean(real_sample_interval)

# %%
np.std(real_sample_interval)

# %%
noise_input = np.array(h5f['noise_input']['data'].tolist())
t_noise_input = h5f['noise_input']['timestamp']

noise_avg = np.array(h5f['noise_avg']['data'].tolist())
t_noise_avg = h5f['noise_avg']['timestamp']

ichan = 0
plt.plot(t_noise_input, noise_input[:, ichan])
plt.plot(t_noise_avg, noise_avg[:, ichan])

# %%
# time between each noise sample
real_sample_interval = np.diff(t_noise_input)
plt.hist(real_sample_interval,
         bins=np.arange(start=0, stop=max(real_sample_interval), step=1e-3))
plt.xlabel(f'Time between samples ({np.mean(real_sample_interval) :.4} '
           f'+- {np.std(real_sample_interval) :.4} s)')
plt.ylabel('Samples')
plt.savefig('real_sample_interval.png')
# %%
# time it takes to calculate and output a rolling average on a noise sample
noise_to_avg_time = t_noise_avg - t_noise_input[:t_noise_avg.shape[0]]
plt.hist(noise_to_avg_time,
         bins=np.arange(start=0, stop=max(noise_to_avg_time), step=1e-3))
plt.xlabel(f'Noise to rolling avg time: ({np.mean(noise_to_avg_time) :.4} '
           f'+- {np.std(noise_to_avg_time) :.4} s)')
plt.ylabel('Samples')
plt.savefig('noise_to_avg_time.png')
# %%
