#!/usr/bin/env python
# thresholdExtractor.py
# Kevin Bodkin
# July 2020



import numpy as np
from scipy import signal as spSignal
from scipy import io
import os, sys, redis
from struct import unpack, pack
from datetime import datetime as dt
from time import sleep

# try this without cython to start
#import cython
#cimport numpy as np


# pathway to redisTools.py
#if __name__ == '__main__': # allow us to run this from inside of proc, for testing sake
#   sys.path.insert(1,'../../lib/redisTools')
#else:
#   sys.path.insert(1,'../lib/redisTools/')
sys.path.insert(1,'../lib/redisTools/')
from redisTools import get_parameter_value
threshold_yaml = 'thresholdExtraction.yaml'
cerebusAdapter_yaml = 'cerebusAdapter.yaml'


###############################################################
## Define supporting functions
###############################################################


# turn the bytecode dict into a python array
def numpy_import(inDict, dataArray, sampTimes, packetLength, numChannels): 
    # wow this is so much easier in the array method :)
    dataArray[:,:] = np.reshape(unpack('h' * packetLength * numChannels, inDict[b'samples']),(numChannels,packetLength))
    sampTimes[:] = np.array(unpack('I' * packetLength, inDict[b'timestamps']))


# -----------------------------------------------------------

# prep the filtered and thresholded data for export
def numpy_export(crossDict, filtDict, rConnection):
    ''' 
    this needs to take the threshold crossing times and filtered data and put it into the Redis stream
    Threshold crossings needs just the time and channel. Since we're thresholding a ms at a time,
    we can just use the ts at the start and end to align it for offline analysis
    
    Since we have two different streams we're pushing into, we'll do it with
    a pipeline '''
    p = rConnection.pipeline() # create a new pipeline
    p.xadd('thresholdCrossings', crossDict) # thresholdCrossings stream -- assuming I've already set it up properly below
    p.xadd('filteredCerebusAdapter', filtDict) # add the filtered stuff to the pipeline
     
    p.execute() # send it brah

# -----------------------------------------------------------
    

# connect to redis
def connect_to_redis(threshold_yaml):
    redis_ip = get_parameter_value(threshold_yaml,'redis_ip')
    redis_port = get_parameter_value(threshold_yaml,'redis_port')
    r = redis.Redis(host = redis_ip, port = redis_port, db = 0)
    print("[thresholdExtractor] Connecting to Redis with IP :", redis_ip, ", port: ", redis_port)
    return r


# -----------------------------------------------------------
### Various filter versions
# rather than having a logic process inside of the loop, we just
# initialize to a different function depending on what we are
# wanting to do.


# causal filtering, no demean
def causal_noDemean_data(data, filtData, sos, zi): 
    filtData[:,:],zi[:,:] = spSignal.sosfilt(sos, data, axis=1, zi=zi)


# causal filtering, demean
def causal_demean_data(data, filtData, sos, zi):
    data-= data.mean(axis=0,keepdims=True)
    filtData[:,:],zi[:,:] = spSignal.sosfilt(sos,data, axis=1, zi=zi)


# -----------------------------------------------------------


# calculate threshold values
def calc_thresh(r, threshMult, readCalls, packetLength, numChannels,sos,zi):
    xrev_receive = r.xrevrange('cerebusAdapter',count = readCalls) # receive
    # thresholds = np.empty((numChannels,1),dtype=np.float32) # threshold array
    readArray = np.empty((numChannels,readCalls * packetLength),dtype=np.float32)
    filtArray = np.empty((numChannels,readCalls * packetLength),dtype=np.float32)
    readTimes = np.empty((readCalls*packetLength))

    for ii in range(0,readCalls): # switch it all into an array
        indStart,indEnd = ii*packetLength,(ii+1)*packetLength
        numpy_import(xrev_receive[ii][1], readArray[:,indStart:indEnd], readTimes[indStart:indEnd], packetLength, numChannels) 
    
    filter_data(readArray,filtArray,sos,zi)
    thresholds = (threshMult * np.sqrt(np.mean(np.square(filtArray),axis=1))).reshape(-1,1)
    return thresholds
    


###############################################################
## Set up data buffers etc
###############################################################

# parameters for data sizing etc
numChannels = get_parameter_value(cerebusAdapter_yaml,'num_channels') # number of channels
packetLength = get_parameter_value(cerebusAdapter_yaml,'samples_per_redis_stream') # the number of 30k samples we should be getting per channel per xread 
cerPack = get_parameter_value(threshold_yaml,'adapter_packet_num') # number of cerebus adapter packets to get per xread call
crossDict = {b'tsStart':b'', b'tsStop':b'',b'samples':b'',b'sampleTimes':b''} # initialize the thresholdCrossing dictionary for writing back to the redis stream
filtDict = {b'sampleTimes':b'',b'samples':b''}



###############################################################
## Prepare filters etc
###############################################################

# filter information
fs = get_parameter_value(threshold_yaml,'sampling_frequency')
butOrder = get_parameter_value(threshold_yaml,'butterworth_order')
butLow = get_parameter_value(threshold_yaml,'butterworth_lowercutoff')
butHigh = get_parameter_value(threshold_yaml,'butterworth_uppercutoff')
demean = get_parameter_value(threshold_yaml, 'enableCAR')
causal = get_parameter_value(threshold_yaml, 'causalEnable')

# set up filter
nyq = .5 * fs
sos = spSignal.butter(butOrder, [butLow/nyq, butHigh/nyq], btype = 'bandpass', analog=False, output='sos') # set up a filter
zi_flat = spSignal.sosfilt_zi(sos) # initialize the state of the filter
zi = np.zeros((zi_flat.shape[0],numChannels,zi_flat.shape[1])) # so that we have the right number of dimensions
for ii in range(0,numChannels): # deal out the filter initialization
   zi[:,ii,:] = zi_flat


# set up which filtering function to use, so that we don't have to do this logic during our main loops 
if causal and (not demean):
    filter_data = causal_noDemean_data
    print('[thresholdExtractor] Loading %d order, [%f %f] hz bandpass causal filter' % (butOrder, butLow, butHigh))

elif causal and demean:
    filter_data = causal_demean_data
    print('[thresholdExtractor] Loading %d order, [%f %f] hz bandpass causal filter with CAR' % (butOrder, butLow, butHigh))

elif (not causal) and (not demean):
    filter_data = causal_noDemean_data
    print('[thresholdExtractor] Loading %d order, [%f %f] hz bandpass causal filter. Acausal not implemented yet!' % (butOrder, butLow, butHigh))

elif (not causal) and demean:
    filter_data = causal_demean_data
    print('[thresholdExtractor] Loading %d order, [%f %f] hz bandpass causal filter with CAR. Acausal not implemented yet!' % (butOrder, butLow, butHigh))




# data chunks for querying from the RT rig
dataBuffer = np.zeros((numChannels,packetLength * cerPack),dtype=np.float32) # we'll be storing the filter state, so don't need a circular buffer
filtBuffer = np.zeros((dataBuffer.shape),dtype=np.float32)
sampTimes = np.zeros((packetLength*cerPack,),dtype='uint32') # noneed to run a float, we're not going to be modifiying these at all.
print(sampTimes.dtype)

# initial data read -- this is to allow us to test using old redis dump files
prevKey = get_parameter_value(threshold_yaml, 'start_key') # initial key to use. Will either be $ or 0 



###############################################################
## main loop
###############################################################

### connecting to redis
r = connect_to_redis(threshold_yaml)
#r.set('thresholdExtractor_working',0)
print('[thresholdExtractor] entering main loop')


# thresholding settings
threshMult = get_parameter_value(threshold_yaml,'thresh_mult') # pull in the threshold multiplier
readCalls = get_parameter_value(threshold_yaml,'thresh_read_calls') # need enough data to calculate variance etc
thresholds = calc_thresh(r, threshMult, readCalls, packetLength, numChannels, sos, zi) # get the array
r.xadd('thresholdValues',{b'thresholds':thresholds.astype('short').tostring()}) # push it into a new redis stream. 
# interesting note for putting data back into redis: we don't have to use pack, since it's already stored as a byte object in numpy. 
# wonder if we can take advantage of that for the unpacking process too

# start time stamping
'''tDelta = [dt.now(), dt.now()]
numLoop = 10000
tDeltaLog = np.empty(numLoop,dtype=dt)
loopInc = 0'''

while True:
   # wait to get data from cerebus stream, then parse it
   #  xread is a bit of a pain: it outputs data as a list of tuples holding a dict
   cerPackInc = 0 # when we're needing to stick multiple packets in the same array
   xread_receive = r.xread({'cerebusAdapter':prevKey}, block=0, count=cerPack)[0][1]
   prevKey = xread_receive[-1][0] # entry number of last item in list
   for xread_tuple in xread_receive: # run each tuple individually
      indStart,indEnd = cerPackInc*packetLength,(cerPackInc+1)*packetLength
      numpy_import(xread_tuple[1], dataBuffer[:,indStart:indEnd], sampTimes[indStart:indEnd], packetLength, numChannels)
      cerPackInc += 1

   # start and stop timestamps for the threshold dict
   crossDict[b'tsStart'] = sampTimes[0].tostring()
   crossDict[b'tsStop'] = sampTimes[-1].tostring()



   # increment the "working" flag -- not enabled at this moment
   # r.incr('thresholdExtractor_working')


   # filter the data and find threshold times
   filter_data(dataBuffer, filtBuffer, sos, zi)
   filtDict[b'sampleTimes'] = sampTimes.tostring()
   filtDict[b'samples'] = filtBuffer.astype('short').tostring()
   # is there a threshold crossing in the last ms
   # find for each channel along the first dimension, keep dims, pack into a byte object and put into the thresh crossings dict
   crossDict[b'sampleTimes'] = sampTimes.tostring()
   crossDict[b'samples'] = np.append(np.zeros((numChannels,1)),((filtBuffer[:,1:] < thresholds) & (filtBuffer[:,:-1] >= thresholds)),axis=1).astype('short').tostring()
   #crossDict[b'samples'] = np.any(filtBuffer <= thresholds,axis=1, keepdims=True).astype('short').tostring()
    
   # send data back to the streams
   numpy_export(crossDict, filtDict, r)
   

   # check our loop timing
   '''tDelta = [dt.now(), tDelta[0]]
   tDeltaLog[loopInc] = (tDelta[0]-tDelta[1])
   if tElapse > 1000:
       print('[thresholdExtractor] tDelta: ', tElapse, ' us')
   
   loopInc += 1'''


'''
print('Mean loop time: ', np.mean(tDeltaLog))
print('Max loop time: ', np.max(tDeltaLog))
print('Min loop time: ', np.min(tDeltaLog))
print('number of zeros: ', sum(tDeltaLog == 0))
'''





