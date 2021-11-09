#! /usr/bin/env python
# redis_to_Matlab.py
# 
# loads thresholds and filtered data from redis and puts them into a dict, then exports to .mat
# using scipy.io

from redis import Redis
from scipy import io
import numpy as np
from struct import unpack
from sys import getsizeof


r = Redis('localhost','6379')

pageSize = 1000 # number of packets per xread call

FN_filt = 'redis_export_filt.mat'
FN_thresh = 'redis_export_thresh.mat'
FN_raw_neural = 'redis_export_raw_neural.mat'
#FN_raw_EMG = 'redis_export_raw_EMG.mat'
num_channels = 5
num_samples = 30
#FN_raw_task = 'redis_export_raw_task.mat'

filtLength = r.xinfo_stream(b'filteredCerebusAdapter')['length']
threshLength = r.xinfo_stream(b'thresholdCrossings')['length']
rawNeuralLength = r.xinfo_stream(b'continuousNeural')['length']
#rawTaskLength = r.xinfo_stream(b'taskInput')['length']
#rawEMGLength = r.xinfo_stream(b'rawEMG')['length']

readLocn_filt = 0
readLocn_thresh = 0
readLocn_Neural_raw = 0
readLocn_Task_raw = 0
readLocn_EMG_raw = 0



# filtered data
print('--------------------------------')
print('converting filtered data')
filt_dict = {'samples':np.zeros((num_channels,filtLength*num_samples),dtype='short'),'timestamps':np.zeros((filtLength*30),dtype='uint32')}
pageNum = 0
indStart = 0
#for a in range(0,60):
while(1):
   try:
      for xreadPack in r.xread({'filteredCerebusAdapter':readLocn_filt}, count=pageSize, block=None)[0][1]:
         indEnd = indStart + num_samples
         filt_dict['samples'][:,indStart:indEnd] = np.reshape(unpack('h'*num_channels*num_samples,xreadPack[1][b'samples']),(num_channels,num_samples))
         filt_dict['timestamps'][indStart:indEnd] = np.array(unpack('I'*num_samples,xreadPack[1][b'timestamps']))
         readLocn_filt = xreadPack[0]
         indStart = indEnd
   except:
        print(indStart)
        break 
   pageNum += 1

print('saving  file')
#print('Size of sample dict:',getsizeof(filt_dict['filt_samples']))
#print('Size of timestamps dict:',getsizeof(filt_dict['filt_timestamps']))
io.savemat(FN_filt,filt_dict,do_compression=True)
del filt_dict


# threshold crossings
print('--------------------------------')
print('converting threshold data')
thresh_dict = {'crossings':np.zeros((threshLength,num_channels),dtype='short'),'timestamps':np.zeros((threshLength),dtype='uint32')}
pageNum = 0
indStart = 0
#for a in range(0,60):
while(1):
    try:
        for xreadPack in r.xread({'thresholdCrossings':readLocn_thresh}, count=pageSize, block=None)[0][1]:
            indEnd = indStart + 1
            thresh_dict['crossings'][indStart:indEnd,:] = np.reshape(unpack('h'*num_channels,xreadPack[1][b'crossings']),(num_channels,))
            thresh_dict['timestamps'][indStart:indEnd] = np.array(unpack('I',xreadPack[1][b'timestamps']))
            readLocn_thresh = xreadPack[0]
            indStart = indEnd
    except:
        print(indStart)
        break    
    pageNum += 1

print('saving  file')
io.savemat(FN_thresh,thresh_dict,do_compression=True)
del thresh_dict


# raw data
print('--------------------------------')
print('converting raw data')
raw_neural_dict = {'samples':np.zeros((num_channels,rawNeuralLength*num_samples),dtype='short'),'timestamps':np.zeros((rawNeuralLength*num_samples,),dtype='uint32'),'BRANDS_time':np.zeros((rawNeuralLength*num_samples,),dtype='uint32'),'udp_recv_time':np.zeros((rawNeuralLength*num_samples,),dtype='uint32')}
pageNum = 0
indStart_neural = 0
#indStart_task = 0
#for a in range(0,60): # I think this should give us about a minute of data -- 1000 samples/page, samples == 1 ms
while(1):
    try:
        for xreadPack in r.xread({'continuousNeural':readLocn_Neural_raw}, count=pageSize, block=None)[0][1]:
            indEnd_neural = indStart_neural + num_samples
            raw_neural_dict['samples'][:,indStart_neural:indEnd_neural] = np.reshape(unpack('h'*num_channels*num_samples,xreadPack[1][b'samples']),(num_channels,num_samples))
            raw_neural_dict['timestamps'][indStart_neural:indEnd_neural] = np.array(unpack('I'*num_samples,xreadPack[1][b'timestamps']))
            cerebusAdapter_time = np.reshape(unpack('ll'*num_samples,xreadPack[1][b'BRANDS_time']),(num_samples,2))
            udp_time = np.reshape(unpack('ll'*num_samples,xreadPack[1][b'udp_recv_time']),(num_samples,2))
            for ii in range(0,num_samples):
                raw_neural_dict['BRANDS_time'][indStart_neural+ii] = cerebusAdapter_time[ii,0]*1000000 + cerebusAdapter_time[ii,1]
                raw_neural_dict['udp_recv_time'][indStart_neural+ii] = udp_time[ii,0]*1000000 + udp_time[ii,1]
            readLocn_Neural_raw = xreadPack[0]
            indStart_neural = indEnd_neural
    except:
        break


print('saving  file')
io.savemat(FN_raw_neural,raw_neural_dict,do_compression=True)
del raw_neural_dict

'''
# task data
print('--------------------------------')
print('converting task data')
pageNum = 0
indStart_task = 0
raw_task_dict = {'samples':np.zeros((rawTaskLength,2),dtype='short'),'timestamps':np.zeros((rawTaskLength,),dtype='uint32'),'BRANDS_time':np.zeros((rawTaskLength,),dtype='uint32'),'udp_recv_time':np.zeros((rawTaskLength,),dtype='uint32')}
for a in range(0,6):
    for xreadPack in r.xread({'taskInput':readLocn_Task_raw}, count=pageSize, block=None)[0][1]:
      try:
        indEnd_task = indStart_task + 1
        raw_task_dict['samples'][indStart_task:indEnd_task,:] = np.reshape(unpack('h'*2,xreadPack[1][b'samples']),(1,2))
        raw_task_dict['timestamps'][indStart_task:indEnd_task] = np.array(unpack('I',xreadPack[1][b'timestamps']))
        cerebusAdapter_time = np.reshape(unpack('ll',xreadPack[1][b'BRANDS_time']),(1,2))
        udp_time = np.reshape(unpack('ll',xreadPack[1][b'udp_recv_time']),(1,2))
        raw_task_dict['BRANDS_time'][indStart_task] = cerebusAdapter_time[0,0]*1000000 + cerebusAdapter_time[0,1]
        raw_task_dict['udp_recv_time'][indStart_task] = udp_time[0,0]*1000000 + udp_time[0,1]
        readLocn_Task_raw = xreadPack[0]
        indStart_task = indEnd_task
      except:
        pass
     
    pageNum += 1

print('saving  file')
io.savemat(FN_raw_task,raw_task_dict,do_compression=True) #will this work?
del raw_task_dict



# EMG data
print('--------------------------------')
print('converting EMG data')
pageNum = 0
indStart_EMG = 0
raw_EMG_dict = {'samples':np.zeros((rawEMGLength*10,12),dtype='short'),'timestamps':np.zeros((rawEMGLength*12,),dtype='uint32'),'BRANDS_time':np.zeros((rawEMGLength*12,),dtype='uint32'),'udp_recv_time':np.zeros((rawEMGLength*12,),dtype='uint32')}
for a in range(0,30):
    for xreadPack in r.xread({'rawEMG':readLocn_EMG_raw}, count=pageSize, block=None)[0][1]:
      try:
        indEnd_EMG = indStart_EMG + 10
        raw_EMG_dict['samples'][indStart_EMG:indEnd_EMG,:] = np.reshape(unpack('h'*12*10,xreadPack[1][b'samples']),(10,12))
        raw_EMG_dict['timestamps'][indStart_EMG:indEnd_EMG] = np.array(unpack('I'*10,xreadPack[1][b'timestamps']))
        cerebusAdapter_time = np.reshape(unpack('ll'*10,xreadPack[1][b'BRANDS_time']),(10,12))
        udp_time = np.reshape(unpack('ll'*10,xreadPack[1][b'udp_recv_time']),(10,12))
        for ii in range(0,10):
          raw_neural_dict['BRANDS_time'][indStart_neural+ii] = cerebusAdapter_time[ii,0]*1000000 + cerebusAdapter_time[ii,1]
          raw_neural_dict['udp_recv_time'][indStart_neural+ii] = udp_time[ii,0]*1000000 + udp_time[ii,1]
        readLocn_EMG_raw = xreadPack[0]
        indStart_EMG = indEnd_EMG
      except:
        pass
     
    pageNum += 1

print('saving  file')
io.savemat(FN_raw_EMG,raw_EMG_dict,do_compression=True) #will this work?
del raw_EMG_dict
''' 
