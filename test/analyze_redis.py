# %%
from datetime import datetime
from struct import unpack
from redis import Redis
from ctypes import Structure, c_long
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


class timeval(Structure):
    """
    timeval struct from sys/time.h
    """
    _fields_ = [("tv_sec", c_long), ("tv_usec", c_long)]


redis_ip = "127.0.0.1"
redis_port = 6379
r = Redis(host=redis_ip, port=redis_port)

# %%
reply_id = b'0-0'
entries = []
while True:
    reply = r.xread({b'mouse_ac': reply_id}, count=1)
    if len(reply) > 0:
        reply_id, cursorFrame = reply[0][1][0]
    else:  # done reading
        break

    # Unpack the x y positions of the cursor
    unpackString = '3h'
    x_pos, y_pos, touch = unpack(unpackString, cursorFrame[b'samples'])

    # Unpack the timestamp
    ts = timeval.from_buffer_copy(cursorFrame[b'timestamps'])
    timestamp = datetime.fromtimestamp(ts.tv_sec + ts.tv_usec * 1e-6)

    entry = dict(x=x_pos, y=y_pos, touch=touch, timestamp=timestamp)
    entries.append(entry)
# %%
df = pd.DataFrame(entries)

# %%
time_between_reads = df['timestamp'].diff().values.astype(np.float)[1:]
time_between_reads = time_between_reads[1:]  # remove first entry (NaN)
time_between_reads *= 1e-6  # convert nanoseconds to milliseconds
plt.hist(time_between_reads, bins=50)
plt.yscale('log')

plt.xlabel('Time between successive samples (milliseconds)')
plt.ylabel('Number of Samples')

tbr_std = np.std(time_between_reads)
tbr_mean = np.mean(time_between_reads)
plt.title('Sampling period: 'f'{tbr_mean :.4f} +- {tbr_std :.4f} ms')

plt.savefig('time_between_cursor_readings.png')
# %%
# How many samples are we missing?
timestamps = df['timestamp'].values
sampling_rate = 1000  # Hz
# recording duration in seconds
total_duration = (timestamps[-1] - timestamps[0]).astype(np.float) * 1e-9
# number of samples we recorded
actual_n_samples = len(timestamps)
# number of samples we expect based on the duration of recording
expected_n_samples = np.floor(total_duration * sampling_rate)
print(f'We are missing {expected_n_samples - actual_n_samples :.0f} samples')
# %%
