import redis
import math
import scipy.signal
import numpy as np
import pandas as pd
import scipy.io
import signal
import os

################################################
## Initialzing Redis
################################################

print("[pipe] Initializing redis...")
r = redis.Redis(host='127.0.0.1',port=6379, db=0)

################################################
## Compute the coefficients for butterworth filtering
################################################

# TODO: READ THIS FROM YAML FILE

nyq      = 0.5 * 1000
butOrder = 4
butLow   = 78
butHigh  = 200
b,a      = scipy.signal.butter(butOrder,[butLow/nyq, butHigh/nyq], btype='bandpass', analog=False)

print("[pipe] Butterworth coefficients: Order: %d, [%f, %f]..." % (butOrder, butLow, butHigh))

r.set("pipe_working",0)

################################################
## Main loop
################################################


print("[pipe] Entering while loop...")

os.kill(os.getppid(), signal.SIGUSR2)

while True:

# Block until we get a signal from timer

    r.xread({"timer":"$"},block=0)

# Increment flag that we're getting to work

    r.incr("pipe_working")

# Read 20ms worth of data

    data = r.xrevrange("streamUDP", count=20)

# Now convert the data to a T X N matrix, where N is the number of channels
# and T is the duration of time for new data

    matrix = np.array([list(x[1].values()) for x in data], dtype=np.float32)

# Now apply common value averaging

    means = matrix.mean(axis=0)
    matrix = np.apply_along_axis(lambda row : row - means, axis = 1, arr = matrix)

# Now apply butterworth filtering

    matrix = np.apply_along_axis(lambda col : scipy.signal.lfilter(b,a,col), axis = 0, arr = matrix)

# Take the sum of the squares. And then take the mean of this
    power = np.apply_along_axis(np.square, axis = 0, arr = matrix).mean(axis=0)

# Stream this data on redis

    streamDict = { ("power" + str(ind)) : str(x) for ind, x in enumerate(power) }
    r.xadd("pipe",streamDict)

    # print(streamDict)

# Decrement flag that we're done work

    r.decr("pipe_working")


