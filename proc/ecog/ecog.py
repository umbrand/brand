# Generate ECOG 
# The goal here is to look into existing ECOG data and then spit out the results in a predictable fashion
# First kick at the can


## Imports

import socket
import sched, time
from datetime import timedelta
import json
import redis
import scipy.io
import yaml
import pandas as pd
import math
from apscheduler.schedulers.blocking import BlockingScheduler
import os
import struct
import numpy as np




r = redis.StrictRedis(host='localhost', port=6379, db=0)

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) # UDP
server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

#############################################
#############################################
## Load the YAML file
#############################################
#############################################
def initializeRedis():
    with open('ecog.yaml') as file:
        yamlData = yaml.safe_load(file)

    for record in yamlData:
        if type(record['value']) == bool:
            if record['value']:
                record['value'] = 1
            else:
                record['value'] = 0
       
        print("Record: ", record['name'], ", Value: ", record['value'], ", Type: ", type(record['value']))

        r.set(record['name'], record['value'])

    r.set("indStart",0)
    


#############################################
#############################################
## Configure the socket
#############################################
#############################################

# First we bind a socket and then make it reusable.
# Then we enable broadcasting mode


#############################################
#############################################
## Loading the .mat files of ECoG data
#############################################
#############################################

def loadMatEcogData(matFileName):
    matFile = scipy.io.loadmat( matFileName, squeeze_me = True, struct_as_record = False)
    return pd.DataFrame(matFile['data'] )


#############################################
#############################################
## Callback function
#############################################
#############################################

# First determine the frequency at which we're sending data
# Next, see if we're enable, if we are not enabled then call back again and abort
# Compute how many rows we should be sending, and then send the rows

def broadcastData(data):

    if r.get("enable") == b'0':
        return
    

    broadcastInterval = float(r.get("broadcastInterval"))
    samplingFrequency = float(r.get("samplingFrequency"))
    numRows           = math.floor(samplingFrequency * broadcastInterval)
    numCols           = data.shape[1]
    indStart          = int(r.get("indStart"))
    indEnd            = indStart + numRows

    s = struct.Struct(str(numRows * data.shape[1]) + "h")

    toSend = s.pack(*data.iloc[indStart:indEnd].values.flatten())

    broadcastPort = int(r.get("broadcastPort"))
    server.sendto(toSend, ('<broadcast>', broadcastPort))

    print(broadcastInterval, samplingFrequency, numRows, len(toSend), indStart)

    nextStart = (indStart + numRows) % data.shape[0]
    r.set("indStart",nextStart)


## The main event


if __name__ == '__main__':

    initializeRedis()

    fileName = '/home/david/code/kaiMillerSpeech/rawdata/speech_basic/data/bp_verbs.mat'
    # data     = loadMatEcogData(fileName)
    data = pd.DataFrame([np.zeros(48, dtype='int16')+x for x in range(10000)])

    broadcastInterval = float(r.get("broadcastInterval"))

    
    

    scheduler = BlockingScheduler()
    hBroadcast = scheduler.add_job(lambda: broadcastData(data), 'interval', seconds=broadcastInterval)

    print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass



# scheduler.enter(broadcastInterval, 1, broadcastData, (indStart,))

# if len(sys.argv) == 1:
#   fileName = '/home/david/code/kaiMillerSpeech/rawdata/speech_basic/data/bp_verbs.mat'
# else:
#     fileName = sys.argv[1]

