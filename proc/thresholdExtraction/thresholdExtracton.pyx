import redis
import numpy as np
from scipy import signal as spSignal
from scipy mport io
import os, sys, redis

# pathway to redisTools.py
sys.path.insert(1,'../../lib.redisTools/')
from redisTools import get_parameter_value
YAML_FILE = 'thresholdExtraction.yaml'

###############################################################
## Connect to Redis
###############################################################

redis_ip = get_parameter_value(YAML_FILE,'redis_ip')
redis_port = get_parameter_value(YAML_FILE,'redis_port')
print("[thresholdExtractor] Connecting to Redis with IP :" , redis_IP, ", port: " redis_port)
r = redis.Redis(host = redis_ip, port = redis_port, db = 0)



###############################################################
## Prepare filters etc
###############################################################
fs = get_parameter_value(YAML_FILE,'sampling_frequency')
butOrder = get_parameter_value(YAML_FILE,'butterworth_order')
butLow = get_parameter_value(YAML_FILE,'butterworth_lowercutoff')
butHigh = get_parameter_value(YAML_FILE,'butterworth_uppercutoff')

nyq = .5 * fs
b,a = scipy.signal.butter(butOrder, [butLow/nyq, butHigh/nyq], btype = 'bandpass', analog=False)

print('[thresholdExtractor] Filtering with %d order, [%f %f] hz bandpass filter' % (butOrder, butLow, butHigh))

numChannels = get_parameter_value(YAML_FILE,'num_channels')
bufferLength = get_parameter_value(YAML_FILE,'buffer_length')
