#!/usr/bin/env python
# thresholdExtractor.py
# Kevin Bodkin
# July 2020



import redis
import numpy as np
from scipy import signal as spSignal
from scipy import io
import os, sys, redis
from struct import unpack, pack
from datetime import datetime as dt

# try this without cython to start
#import cython
#cimport numpy as np


# pathway to redisTools.py
if __name__ == '__main__': # allow us to run this from inside of proc, for testing sake
   sys.path.insert(1,'../../lib/redisTools')
else:
   sys.path.insert(1,'../lib/redisTools/')
from redisTools import get_parameter_value
threshold_yaml = 'thresholdExtraction.yaml'
cerebusAdapter_yaml = 'cerebusAdapter.yaml'


###############################################################
## Define supporting functions
###############################################################


# turn the bytecode dict into a python array
def numpy_import(inDict, outArray, samples): 
    
    chInd = 0  # increment to keep track of which  channel we're on -- not all data in the dict is neural signals

    for ii in inDict.keys():
        if 'chan' in ii.decode('utf-8'):
            outArray[chInd,:] = unpack('h' * samples,inDict[ii])
            chInd += 1

# -----------------------------------------------------------

# prep the filtered and thresholded data for export
def numpy_export(threshDict, filtDict, threshArray, filtArray, rConnection, numSamples):
    chInd = 0 # need to iterate through channel numbers in reverse

    for ii in threshDict.keys():
        if 'chan' in ii.decode():
            threshDict[ii] = pack('h',int(threshArray[chInd]))
            filtDict[ii] = pack('h'*numSamples,filtArray[chInd,:].astype(int))
            chInd += 1
    
    p = rConnection.pipeline() # create a new pipeline
    p.xadd('thresholdCrossings',threshDict) # thresholdCrossings stream
    p.xadd('filt30k',filtDict) # filtered Data stream
    p.execute()
    
# -----------------------------------------------------------
    

# connect to redis
def connect_to_redis(threshold_yaml):
    redis_ip = get_parameter_value(threshold_yaml,'redis_ip')
    redis_port = get_parameter_value(threshold_yaml,'redis_port')
    r = redis.Redis(host = redis_ip, port = redis_port, db = 0)
    print("[thresholdExtractor] Connecting to Redis with IP :", redis_ip, ", port: ", redis_port)
    return r


# -----------------------------------------------------------

# filtering loop
def filter_data(dataBuffer, filtBuffer, sos, demean=True, acausal=False):
    # demean if we're wanting
    if demean:
        dataBuffer -= dataBuffer.mean(axis=0,keepdims=True)

    if acausal:
        filtBuffer[:,:] = spSignal.sosfilt(sos, dataBuffer, axis=1)
    else:
        filtBuffer[:,:] = spSignal.sosfiltfilt(sos, dataBuffer, axis=1)


# -----------------------------------------------------------


# calculate threshold values
def calc_thresh(r, threshMult, readCalls, samplesPerRead, numChannels):
    xrev_receive = r.xrevrange('cerebusAdapter',count = readCalls) # receive
    # thresholds = np.empty((numChannels,1),dtype=np.float32) # threshold array
    readArray = np.empty((numChannels,readCalls * samplesPerRead),dtype=np.float32)
    
    for ii in range(0,readCalls): # switch it all into an array
        numpy_import(xrev_receive[ii][1], readArray[:,ii*samplesPerRead:(ii+1)*samplesPerRead], samplesPerRead) 
    
    thresholds = (threshMult * np.sqrt(np.mean(np.square(readArray),axis=1))).reshape(-1,1)
    return thresholds
    


###############################################################
## Prepare filters etc
###############################################################

# filter information
fs = get_parameter_value(threshold_yaml,'sampling_frequency')
butOrder = get_parameter_value(threshold_yaml,'butterworth_order')
butLow = get_parameter_value(threshold_yaml,'butterworth_lowercutoff')
butHigh = get_parameter_value(threshold_yaml,'butterworth_uppercutoff')

nyq = .5 * fs
sos = spSignal.butter(butOrder, [butLow/nyq, butHigh/nyq], btype = 'bandpass', analog=False, output='sos')

print('[thresholdExtractor] Loading filter : %d order, [%f %f] hz bandpass' % (butOrder, butLow, butHigh))

# parameters for data sizing etc
numChannels = get_parameter_value(cerebusAdapter_yaml,'num_channels') # number of channels
bufferLen = get_parameter_value(threshold_yaml,'buffer_len') # number of times we should do an xread before we filter and find thresholds
sampleLength = get_parameter_value(cerebusAdapter_yaml,'samples_per_redis_stream') # the number of 30k samples we should be getting per channel per xread 
threshDict = {}
for ii in range(0,numChannels-1):
    threshDict[('chan{}'.format(ii)).encode()] = pack('h',int(0))


# data chunks for querying from the RT rig
dataBuffer = np.zeros((numChannels,bufferLen),dtype=np.float32) # keep an additional tap of lag so we don't have to worry about storing the filter state
filtBuffer = np.zeros((dataBuffer.shape),dtype=np.float32)





###############################################################
## main loop
###############################################################

### connecting to redis
r = connect_to_redis(threshold_yaml)
r.set('thresholdExtractor_working',0)
print('[thresholdExtractor] entering main loop')


readInc = 0 # incrementing so that we can get 3 data sets before running the filter loop
# thresholding settings
threshMult = get_parameter_value(threshold_yaml,'thresh_mult') # pull in the threshold multiplier
readCalls = get_parameter_value(threshold_yaml,'thresh_read_calls') # need enough data to calculate variance etc
thresholds = calc_thresh(r, threshMult, readCalls, sampleLength, numChannels) # get the array
# xread_receive = r.xread({'cerebusAdapter':'$'},block=0) # get an initial 
# prevKey = xread_receive[0][1][0][0] # not sure if we're actually going to need this 
tDelta = [dt.now(), 0]

while True:

   # wait to get data from cerebus stream, then parse it
   #  xread is a bit of a pain: it outputs data as a dict in a list of a list of a list.
   # hint for reading: check out the struct python module
   xread_receive = r.xread({'cerebusAdapter':'$'},block=0)
   prevKey = xread_receive[0][1][0][0] # first list: ?; second list: cerebus stream; third list: location in record;
   xread_dict = xread_receive[0][1][0][1]
   # numSamples = int(xread_dict[b'num_samples'].decode())
   dataBuffer[:,:-sampleLength] = dataBuffer[:,sampleLength:]
   numpy_import(xread_dict, dataBuffer[:,-sampleLength:], sampleLength) 

   # increment the "working" flag
   r.incr('thresholdExtractor_working')


   # filter the data and find threshold times
   filter_data(dataBuffer, filtBuffer, sos)
   threshCross = np.sum(filtBuffer[:,sampleLength:] <= thresholds,axis=1) # is there a threshold crossing in the last ms?
      
   # send data back to the streams
   numpy_export(threshDict, xread_dict, threshCross, filtBuffer, r, sampleLength)


   # check our loop timing
   tDelta = [dt.now(), tDelta[0]]
   if (tDelta[0]-tDelta[1]).microseconds > 1000:
       print('[thresholdExtractor] tDelta: ', (tdelta[0]-tDelta[1]).microseconds, 'us')
   








