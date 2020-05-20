import redis
import math
import scipy.signal
import numpy as np
import pandas as pd
import scipy.io
import signal
import os
import sys

cimport numpy


# Pathway to get redisTools.py
sys.path.insert(1, '../../lib/redisTools/')
from redisTools import getSingleValue

YAML_FILE = 'pipe.yaml'

################################################
## Initializing Redis
################################################

redis_ip = getSingleValue(YAML_FILE,"redis_ip")
redis_port = getSingleValue(YAML_FILE,"redis_port")
print("[pipe] Initializing Redis with IP :" , redis_ip, ", port: ", redis_port)
r = redis.Redis(host = redis_ip, port = redis_port, db = 0)

################################################
## Compute the coefficients for butterworth filtering
################################################

# TODO: READ THIS FROM YAML FILE

fs       = getSingleValue(YAML_FILE, 'sampling_frequency')
butOrder = getSingleValue(YAML_FILE, 'butterworth_order')
butLow   = getSingleValue(YAML_FILE, 'butterworth_lowercutoff')
butHigh  = getSingleValue(YAML_FILE, 'butterworth_uppercutoff')

nyq      = 0.5 * fs
b,a      = scipy.signal.butter(butOrder,[butLow/nyq, butHigh/nyq], btype='bandpass', analog=False)

print("[pipe] Butterworth coefficients: Order: %d, [%f, %f]..." % (butOrder, butLow, butHigh))

################################################
## Read from YAML file
################################################

cdef int samples_per_cycle = getSingleValue(YAML_FILE,"samples_per_cycle")
cdef int num_channels      = getSingleValue(YAML_FILE,"num_channels")

# cdef int c_matrix[samples_per_cycle][num_channels]



################################################
## Main loop
################################################

r.set("pipe_working",0)

print("[pipe] Entering while loop...")

# os.kill(os.getppid(), signal.SIGUSR2)

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


