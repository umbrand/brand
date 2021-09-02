#! /usr/bin/env python
# _*_ coding: utf-8 -*-
# exportNWB.py


"""
exportNWB.py

takes data from a dump.rdb snapshot file and exports it as an NWB so that it can be
analyzed in python and matlab in a format that works for many different labs


@author Kevin Human Primate
"""

#from pynwb import NWBFile, TimeSeries
import pynwb
from redis import Redis
from datetime import datetime
from dateutil.tz import tzlocal
import numpy as np
from struct import unpack
from os import getcwd
from os import path as osPath
import sys 


# check to see if we're trying to run this from the base directory or from inside of 'run'
# for debugging purposes when I'm jumping between files a lot
if getcwd().split('/')[-1] == 'realtime_rig_dev':
    sys.path.insert(1,'lib/redisTools/')
else: # assumes we're only one directly above the base
    sys.path.insert(1,'../lib/redisTools/')
from redisTools import get_parameter_value
NWB_yaml = 'exportNWB.yaml'



# connect to redis
try:
    redis_ip = get_parameter_value(NWB_yaml,'redis_ip')
    redis_port = get_parameter_value(NWB_yaml,'redis_port')
    print('[exportNWB] redis_ip: ', redis_ip, ' redis_port: ', redis_port)
    r = Redis(host = redis_ip, port = redis_port)
    print('[exportNWB] Connecting to Redis...')
except:
    print('[exportXDS] Failed to connect to Redis. Exiting.')
    exit()


# assumes that source is a dictionary with fields:
# redisDataType, redisDataName, redisTimestamps, redisSamples, redisPackString, NWBDataType, NWBDataName
dataSourceNames = get_parameter_value(NWB_yaml,'dataSourceNames') # get the name of all of the sources expected
if isinstance(dataSourceNames,str): # change it from a string to list if necessary
    dataSourceNames = [dataSourceNames]

# create the NWBFile
startTime = datetime.today()  # need to figure out how to get this out of redis
createDate = datetime.today() # we're making the file now, aren't we?
sessionDescription = get_parameter_value(NWB_yaml,'sessionDescription')
nwbfile = pynwb.NWBFile(session_description = sessionDescription,
                        identifier = 'NWB123',
                        session_start_time = startTime,
                        file_create_date = createDate)


for sourceName in dataSourceNames:
    source = get_parameter_value(NWB_yaml,sourceName) # load relevent info from yaml
    if source['redisDataType'] == 'stream':
        pageLength = 10000 # pull out data x points at a time
        startKey = '-'   
        npInd = 0 
        # bring in all of the import and unpacking variables
        # this is mostly just to make the code in the main loop more readable
        samplesPerPack = source['samplesPerPack']
        dataWidth = source['dataWidth']
        redisPackString = source['redisPackString']*samplesPerPack*dataWidth
        redisTimePack = source['redisTimePack']*samplesPerPack
        redisDataName = source['redisDataName']
        redisSamples = source['redisSamples']
        redisTimestamps = source['redisTimestamps']
       
        # pre-allocating arrays just to make everything run more quickly 
        samples = np.empty([r.xlen(redisDataName.encode())*samplesPerPack,dataWidth],dtype=np.float)
        timestamps = np.empty(r.xlen(redisDataName.encode())*samplesPerPack,dtype=np.float)
        pageFrame = r.xrange(redisDataName,min=startKey,count=pageLength) # funky full dictionary
        
        while len(pageFrame) > 0:
            for frame in pageFrame:
                dataIndex = [r for r in range(npInd,npInd+samplesPerPack)] # gonna have to use this a few times
                samples[dataIndex,:] = np.array(unpack(redisPackString,frame[1][redisSamples.encode()]), dtype=np.float).reshape([samplesPerPack,dataWidth])
                timestamps[dataIndex] = np.array(unpack(redisTimePack,frame[1][redisTimestamps.encode()]), dtype=np.float)
                npInd += samplesPerPack # update to the next block of samples
            startKey = pageFrame[-1][0].decode('utf-8').split('-') # get the last entry key, change from byte to string, split by the '-' in the middle
            startKey = startKey[0] + '-' + str(int(startKey[1])+1) # increment the second half of the key, recombine
            pageFrame = r.xrange(redisDataName,min=startKey,count=pageLength) # funky full dictionary
    
        if source['NWBDataType'] == 'TimeSeries':
            times = pynwb.TimeSeries(name=source['NWBDataName'],
                               data=samples,
                               unit=source['sampleUnits'],
                               timestamps=timestamps)
#        if source['NWBDataType'] == 'ElectricalSeries':
#            times = pynwb.ElectricalSeries(name=source['NWBDataName'],
#                               data=samples,
#                               unit=source['sampleUnits'],
#                               timestamps=timestamps)
#        if source['NWBDataType'] == 'SpatialSeries':
#            times = pynwb.ElectricalSeries(name=source['NWBDataName'],
#                               data=samples,
#                               unit=source['sampleUnits'],
#                               timestamps=timestamps)

         

    nwbfile.add_acquisition(times) # write it to the NWB file





# close everything up
nwbFileName = get_parameter_value(NWB_yaml,'nwbFileName')    # get the filename
with pynwb.NWBHDF5IO(nwbFileName, 'w') as io:             # open up a file
    io.write(nwbfile)                               # and write it







