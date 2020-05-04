# This is the neural feature extraction pipeline. Here's what I need it to do
# 1. Everything timestep, query redis for new data
# 2. Examine the data timestamps to see which ones were taken.
# 3. Compute an over-fill or underfill. Here's one way to ipmlement this:
#   - Say we're computing at 10ms. So I collect 20ms worth of data. Put this all into a dataframe
#   - Next I look at the timestamps of those data and then decide which are greater than the last timestamp I have.
#   - I should have 10 rows. If I have more rows I call this overfill, and under I call this overfill.
#   - So this decouples the udpAdapter from the logic of the pipe. It means that I can very quickly (dynamically?) change the timestep at which. 
# I note that the samplingFrequency needs to be known not for the processing logic per se, but for the
# filtering parameters. Computing (b,a) for the notch filtering and butterworth filtering need fs
#
# In the pipe, ecogData is a pandas dataframe. This allows us to take advantage of vectorization
# It would help if I wrote wrapper functions to get float, ints, strings, and lists from Redis
# Since I do it a lot and it's annoying to have to re-invent the wheel. The nice thing is that
# I can use the __name__ function of whatever is calling me so that I can automatically pad strings
# Also useful to have a helper function initialize from YAML file
# 
# TODO: DOuble check that I have implemented CAR correctly with axis=0 and axis=1

## Imports

import math
import scipy.signal
import numpy as np
import pandas as pd
import scipy.io
import redis
import swifter
from apscheduler.schedulers.blocking import BlockingScheduler
import sys

sys.path.insert(1, '../../lib/')
from redisTools import *



r = redis.StrictRedis(host='localhost', port=6379, db=0)

###########################################
## Pipe function
###########################################

def pipe():

    ecogData, stats  = getRawDataFromRedis()

    print(ecogData[0][0])

    ecogData         = applyCommonValueAveraging(ecogData)

    # ecogData         = applyNotchFilter120(ecogData)

    # ecogData         = applyNotchFilter180(ecogData)

    ecogData         = applyButterworthFilter(ecogData)

    neuralFeatures   = getNeuralPower(ecogData)

    # print(neuralFeatures[0])

    # publish(neuralFeatures, statistics)

###########################################
## Components of the pipe
###########################################

def getRawDataFromRedis():

    samplesPerCycle = getInt(r, 'samplesPerCycle')
    redisData       = r.lrange("rawData", 0, samplesPerCycle)
    allChannels     = [np.fromiter(x.split(), dtype = 'int16') for x in redisData]

    return pd.DataFrame(allChannels), 0


# Take the of the columns, and then subtract this from each of the rows
def applyCommonValueAveraging(x):

    means = x.mean(axis=0)
    return x.apply(lambda row: row - means, axis=1)

def applyNotchFilter120(x):
    b = getFloatLRange(r, 'b120', 0, -1)
    a = getFloatLRange(r, 'a120', 0,-1)
    return x.apply(lambda col: scipy.signal.filtfilt(b,a,col))
 
def applyNotchFilter180(x):
    b = getFloatLRange(r, 'b180', 0, -1)
    a = getFloatLRange(r, 'a180', 0, -1)
    return x.apply(lambda col: scipy.signal.filtfilt(b,a,col))

def applyButterworthFilter(x):
    b = getFloatLRange(r, 'b_but', 0, -1)
    a = getFloatLRange(r, 'a_but', 0, -1)
    return x.apply(lambda col: scipy.signal.lfilter(b,a,col))

# Take the mean of (sum of the squares). Axis = 0 means columns
def getNeuralPower(x):

    return x.apply(np.square, axis = 0).mean()

###########################################
## Initialization functions
###########################################

def initializePipeline():

    initializeRedisFromYAML(r, 'pipe')

    fs = getInt(r, 'samplingFrequency')

    butLow   = getInt(r, 'butterworthLowerCutoff')
    butHigh  = getInt(r, 'butterworthUpperCutoff')
    butOrder = getInt(r, 'butterworthOrder')

    nyq = 0.5 * fs
    Q   = 60

    b120, a120 = scipy.signal.iirnotch(120/nyq,Q=Q)
    b180, a180 = scipy.signal.iirnotch(180/nyq,Q=Q)
    
    b_but,a_but = scipy.signal.butter(butOrder,[butLow/nyq, butHigh/nyq], btype='bandpass', analog=False)

    print(b120)

    r.rpush('b120'  , *b120)
    r.rpush('a120'  , *a120)
    r.rpush('b180'  , *b180)
    r.rpush('a180'  , *a180)
    r.rpush('b_but' , *b_but)
    r.rpush('a_but' , *a_but)
    

###########################################
## The main event
###########################################

if __name__ == '__main__':

    initializePipeline()

    samplingFrequency = getInt(r, 'samplingFrequency')
    samplesPerCycle   = getInt(r, 'samplesPerCycle')

    cyclePeriod = samplesPerCycle / samplingFrequency

    # executors = {
    #     # 'default': {'type': 'threadpool', 'max_workers': 20},
    #     # 'processpool': ProcessPoolExecutor(max_workers=5)
    # }
    job_defaults = {
        'coalesce': False,
        'max_instances': 2,
    }

    scheduler   = BlockingScheduler()
    scheduler.add_job(pipe, 'interval', seconds=cyclePeriod)
    # scheduler.add_job(pipe, 'interval', seconds=1)
    # scheduler.configure(executors=executors, job_defaults=job_defaults)
    scheduler.configure(job_defaults=job_defaults)
    scheduler.start()


