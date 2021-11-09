#!/usr/bin/env python
# thresholdExtraction.py
# Kevin Bodkin
# July 2020



import numpy as np
from scipy import signal as spSignal
from scipy import io
import os, sys, signal
from redis import Redis
from struct import unpack, pack
from datetime import datetime as dt
from time import sleep
import argparse

# need to take more advantage of cython
'''import cython
cimport numpy as np'''


# bring in redisTools
from brand import *


###############################################################
## Define supporting functions
###############################################################

# clean exit code
def signal_handler(sig,frame): # setup the clean exit code with a warning
    print('[behaviorFSM] SIGINT received, Exiting')
    sys.exit(0)


# place the sigint signal handler
signal.signal(signal.SIGINT, signal_handler)


# ------------------------------------------------------------
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
def calc_thresh(r, streamName, threshMult, readCalls, packetLength, numChannels, sos, zi):
    xrev_receive = r.xrevrange(streamName, count = readCalls) # receive
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
    

# -----------------------------------------------------------

def pack_string_parser(ioDict):
    if ioDict['sample_type'] in ['int16', 'short']:
        packString = 'h'
    elif ioDict['sample_type'] in ['int32', 'int', 'Int']:
        packString = 'i'
    elif ioDict['sample_type'] in ['uInt32', 'uInt']: 
        packString = 'I'
    elif ioDict['sample_type'] == 'char':
        packString = 'b'
    else:
        return -1
    
    # output string = <#values><var type> -- 10I, 960h etc
    packString = str(ioDict['chan_per_stream'] * ioDict['samp_per_stream']) + packString
    return packString


###############################################################
## Set up argparser so we can cleanly pull from the command line
###############################################################
if __name__ == '__main__':
    argDesc = """
            Python script to find threshold crossings in raw cortical data. It
            filters and finds timepoints when the input signal goes below the 
            calculated value."""
    
    parser = argparse.ArgumentParser(description=argDesc)
    # only argument we have right now is the yaml path location, which defaults to the sharedDev location
    # we should consider having default yamls or something for testing.
    parser.add_argument("yaml", help="path to graph YAML settings file")
    args = parser.parse_args()
    graphYAML = args.yaml


###############################################################
## Set up data buffers etc
###############################################################
# get the list of which channel we're working with 
signalIO = get_node_io(graphYAML, 'thresholdExtraction') 
if len(signalIO['redis_inputs']) > 1:
    sys.exit("We don't support more than one stream input at the moment. If you want more, program it!")
                

inStreamName = list(signalIO['redis_inputs'].keys())[0] # get the name of the input stream
inNode = signalIO['redis_inputs'][inStreamName] # dictionary with the input stream info

# parameters for data sizing etc
numChannels =  inNode['chan_per_stream'] # number of channels
packetLength = inNode['samp_per_stream'] # number of samples per channel per redis entry
packString = pack_string_parser(inNode) # figure out the pack string for the redis stream    
crossDict = {b'crossings':b'',b'timestamps':b''} # initialize the thresholdCrossing dictionary for writing back to the redis stream
filtDict = {b'timestamps':b'',b'samples':b''}



###############################################################
## Prepare filters etc
###############################################################

# filter information
nodeParameters = get_node_parameter_dump(graphYAML, 'thresholdExtraction')
butOrder = nodeParameters['butter_order'] # order of the butterworth filter
butLow = nodeParameters['butter_lowercut'] # lower cutoff frequency
butHigh = nodeParameters['butter_uppercut'] # upper cutoff frequency
demean = nodeParameters['enable_CAR'] # enable common average rejection
causal = nodeParameters['causal_enable'] # likely only going to be doing causal filtering at the moment
fs = inNode['samp_freq'] # this will need to be in the nodes portion then


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
    print('[thresholdExtraction] Loading %d order, [%f %f] hz bandpass causal filter' % (butOrder, butLow, butHigh))

elif causal and demean:
    filter_data = causal_demean_data
    print('[thresholdExtraction] Loading %d order, [%f %f] hz bandpass causal filter with CAR' % (butOrder, butLow, butHigh))

elif (not causal) and (not demean):
    filter_data = causal_noDemean_data
    print('[thresholdExtraction] Loading %d order, [%f %f] hz bandpass causal filter. Acausal not implemented yet!' % (butOrder, butLow, butHigh))

elif (not causal) and demean:
    filter_data = causal_demean_data
    print('[thresholdExtraction] Loading %d order, [%f %f] hz bandpass causal filter with CAR. Acausal not implemented yet!' % (butOrder, butLow, butHigh))




# data chunks for querying from the RT rig
numPacks = nodeParameters['pack_per_call']
dataBuffer = np.zeros((numChannels,packetLength * numPacks),dtype=np.float32) # we'll be storing the filter state, so don't need a circular buffer
filtBuffer = np.zeros((dataBuffer.shape),dtype=np.float32)
sampTimes = np.zeros((packetLength*numPacks,),dtype='uint32') # noneed to run a float, we're not going to be modifiying these at all.
print(sampTimes.dtype)

# initial data read -- this is to allow us to test using old redis dump files
prevKey = '$'



###############################################################
## main loop
###############################################################

# -----------------------------------------------------------
# connect to Redis -- using redisTools
r = initializeRedisFromYAML(graphYAML,'thresholdExtraction')
print('[thresholdExtraction] entering main loop')


# thresholding settings
threshMult = nodeParameters['thresh_mult'] # threshold multiplier, usually around -5 
readCalls = nodeParameters['thresh_calc_len'] # make sure we have enough data to work with
thresholds = calc_thresh(r, inStreamName, threshMult, readCalls, packetLength, numChannels, sos, zi) # get the array
r.xadd('thresholdValues',{b'thresholds':thresholds.astype('short').tostring()}) # push it into a new redis stream. 
# interesting note for putting data back into redis: we don't have to use pack, since it's already stored as a byte object in numpy. 
# wonder if we can take advantage of that for the unpacking process too


while True:
    # wait to get data from cerebus stream, then parse it
    #  xread is a bit of a pain: it outputs data as a list of tuples holding a dict
    cerPackInc = 0 # when we're needing to stick multiple packets in the same array
    xread_receive = r.xread({inStreamName:prevKey}, block=1, count=numPacks)[0][1]
    prevKey = xread_receive[-1][0] # entry number of last item in list
    for xread_tuple in xread_receive: # run each tuple individually
       indStart,indEnd = cerPackInc*packetLength,(cerPackInc+1)*packetLength
       numpy_import(xread_tuple[1], dataBuffer[:,indStart:indEnd], sampTimes[indStart:indEnd], packetLength, numChannels)
       cerPackInc += 1


    # filter the data and find threshold times
    filter_data(dataBuffer, filtBuffer, sos, zi)
    filtDict[b'timestamps'] = sampTimes.tostring()
    filtDict[b'samples'] = filtBuffer.astype('short').tostring()
    # is there a threshold crossing in the last ms
    # find for each channel along the first dimension, keep dims, pack into a byte object and put into the thresh crossings dict
    crossDict[b'timestamps'] = sampTimes[0].tostring()
    crossings = np.append(np.zeros((numChannels,1)),((filtBuffer[:,1:] < thresholds) & (filtBuffer[:,:-1] >= thresholds)),axis=1)
    crossDict[b'crossings'] = np.any(crossings, axis=1).astype('short').tostring()
   
    # send data back to the streams
    numpy_export(crossDict, filtDict, r)
    

    # check our loop timing
    '''tDelta = [dt.now(), tDelta[0]]
    tDeltaLog[loopInc] = (tDelta[0]-tDelta[1])
    if tElapse > 1000:
        print('[thresholdExtraction] tDelta: ', tElapse, ' us')
    
    loopInc += 1'''
 

'''
print('Mean loop time: ', np.mean(tDeltaLog))
print('Max loop time: ', np.max(tDeltaLog))
print('Min loop time: ', np.min(tDeltaLog))
print('number of zeros: ', sum(tDeltaLog == 0))
'''





