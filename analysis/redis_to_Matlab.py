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
from datetime import datetime


r = Redis('localhost','6379')

pageSize = 1000 # number of packets per xread call

rdb_prefix = str(datetime.fromtimestamp(r.info('persistence')['rdb_last_save_time'])).replace(' ','T')
print(rdb_prefix)


FN_filt = rdb_prefix + 'redis_export_filt.mat'
FN_thresh = rdb_prefix + 'redis_export_thresh.mat'
FN_raw_neural = rdb_prefix + 'redis_export_raw_neural.mat'
FN_raw_EMG = rdb_prefix + 'redis_export_raw_EMG.mat'
num_channels = 96
num_samples = 30
FN_raw_task = rdb_prefix + 'redis_export_raw_task.mat'
FN_cursor = rdb_prefix + 'redis_export_cursor.mat'
FN_target = rdb_prefix + 'redis_export_target.mat'

filtLength = r.xinfo_stream(b'filteredCerebusAdapter')['length']
threshLength = r.xinfo_stream(b'thresholdCrossings')['length']
rawNeuralLength = r.xinfo_stream(b'continuousNeural')['length']
rawTaskLength = r.xinfo_stream(b'taskInput')['length']
cursorLength = r.xinfo_stream(b'cursorData')['length']
targetLength = r.xinfo_stream(b'targetData')['length']
rawEMGLength = r.xinfo_stream(b'rawEMG')['length']

readLocn_Neural_raw = 0
readLocn_Task_raw = 0
readLocn_filt = 0
readLocn_thresh = 0
readLocn_cursor = 0
readLocn_target = 0



"""
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
"""

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


"""
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
"""

# task data
print('--------------------------------')
print('converting task data')
pageNum = 0
indStart_task = 0
task_channels = 3
raw_task_dict = {'samples':np.zeros((rawTaskLength,task_channels),dtype='short'),'timestamps':np.zeros((rawTaskLength,),dtype='uint32'),
    'BRANDS_time':np.zeros((rawTaskLength,),dtype='uint32'),'udp_recv_time':np.zeros((rawTaskLength,),dtype='uint32')}
#for a in range(0,6):
while indStart_task<rawTaskLength:
#while True:
    #try:
        for xreadPack in r.xread({'taskInput':readLocn_Task_raw}, count=pageSize, block=None)[0][1]:
            indEnd_task = indStart_task + 1
            raw_task_dict['samples'][indStart_task:indEnd_task,:] = np.reshape(unpack('h'*task_channels,xreadPack[1][b'samples']),(1,task_channels))
            raw_task_dict['timestamps'][indStart_task:indEnd_task] = np.array(unpack('I',xreadPack[1][b'timestamps']))
            cerebusAdapter_time = np.reshape(unpack('ll',xreadPack[1][b'BRANDS_time']),(1,2))
            udp_time = np.reshape(unpack('ll',xreadPack[1][b'udp_recv_time']),(1,2))
            raw_task_dict['BRANDS_time'][indStart_task] = cerebusAdapter_time[0,0]*1000000 + cerebusAdapter_time[0,1]
            raw_task_dict['udp_recv_time'][indStart_task] = udp_time[0,0]*1000000 + udp_time[0,1]
            readLocn_Task_raw = xreadPack[0]
            indStart_task = indEnd_task
    #except:
        #print(indStart_task)
        #break
     

print('saving  file')
io.savemat(FN_raw_task,raw_task_dict,do_compression=True) #will this work?
del raw_task_dict


"""
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
""" 

# cursor data
print('--------------------------------')
print('converting cursor data')
pageNum = 0
indStart_cursor = 0
cursor_dict = {'X':np.zeros((cursorLength,),dtype='int32'),'Y':np.zeros((cursorLength,),dtype='int32'),'sync':np.zeros((cursorLength,),dtype='uint32')}
#for a in range(0,6):
while indStart_cursor<cursorLength:
#while True:
    try:
        for xreadPack in r.xread({'cursorData':readLocn_cursor}, count=pageSize, block=None)[0][1]:
            indEnd_cursor = indStart_cursor + 1
            cursor_dict['X'][indStart_cursor:indEnd_cursor] = np.array(unpack('i',xreadPack[1][b'X']))
            cursor_dict['Y'][indStart_cursor:indEnd_cursor] = np.array(unpack('i',xreadPack[1][b'Y']))
            cursor_dict['sync'][indStart_cursor:indEnd_cursor] = np.array(unpack('I',xreadPack[1][b'sync']))
            readLocn_cursor = xreadPack[0]
            indStart_cursor = indEnd_cursor
    except:
        print(indStart_cursor)
        break

print('saving  file')
io.savemat(FN_cursor,cursor_dict,do_compression=True) #will this work?
del cursor_dict



# target data
print('--------------------------------')
print('converting target data')
pageNum = 0
indStart_target = 0
target_dict = {'X':np.zeros((targetLength,),dtype='int32'),'Y':np.zeros((targetLength,),dtype='int32'),'sync':np.zeros((targetLength,),dtype='uint32'),
    'width':np.zeros((targetLength,),dtype='int32'),'height':np.zeros((targetLength,),dtype='int32'),
    'state':np.zeros((cursorLength,),dtype='int32')}
#for a in range(0,6):
while indStart_target<targetLength:
#while True:
    try:
        for xreadPack in r.xread({'targetData':readLocn_target}, count=pageSize, block=None)[0][1]:
            indEnd_target = indStart_target + 1
            target_dict['X'][indStart_target:indEnd_target] = np.array(unpack('i',xreadPack[1][b'X']))
            target_dict['Y'][indStart_target:indEnd_target] = np.array(unpack('i',xreadPack[1][b'Y']))
            target_dict['width'][indStart_target:indEnd_target] = np.array(unpack('i',xreadPack[1][b'width']))
            target_dict['height'][indStart_target:indEnd_target] = np.array(unpack('i',xreadPack[1][b'height']))
            target_dict['state'][indStart_target:indEnd_target] = np.array(unpack('I',xreadPack[1][b'state']))
            target_dict['sync'][indStart_target:indEnd_target] = np.array(unpack('I',xreadPack[1][b'sync']))
            readLocn_target = xreadPack[0]
            indStart_target = indEnd_target
    except:
        print(indStart_target)
        break

print('saving  file')
io.savemat(FN_target,target_dict,do_compression=True) #will this work?
del target_dict


