import redis
import math
import scipy.signal
import numpy as np
import pandas as pd
import scipy.io



print("[pipe] Initializing redis...")
r = redis.Redis(host='127.0.0.1',port=6379)

# Butterworth filtering
return x.apply(lambda col: scipy.signal.lfilter(b,a,col))


# Get the data from r.xrange

# Apply the Common value averaging

# Apply butterworth filtering

# 


# vals = r.xrange("streamUDP", count=1)
# print(vals)

# This will return an array of entries
# Each entry has [0] --> timestamp
# [1] --> A dictionary
