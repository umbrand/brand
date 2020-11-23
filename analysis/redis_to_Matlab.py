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
FN_raw = 'redis_export_raw.mat'

filtLength = r.xinfo_stream(b'filteredCerebusAdapter')['length']
threshLength = r.xinfo_stream(b'thresholdCrossings')['length']
rawLength = r.xinfo_stream(b'cerebusAdapter')['length']

readLocn_filt = 0
readLocn_thresh = 0
readLocn_raw = 0

filt_dict = {'filt_samples':np.zeros((96,filtLength*30),dtype='short'),'filt_timestamps':np.zeros((filtLength*30),dtype='uint32')}
thresh_dict = {'thresh_samples':np.zeros((96,threshLength*30),dtype='short'),'tsStart':np.zeros((threshLength,),dtype='uint32'),'tsStop':np.zeros((threshLength,),dtype='uint32'),'thresh_timestamps':np.zeros((threshLength*30),dtype='uint32')}
raw_dict = {'raw_samples':np.zeros((96,rawLength*10),dtype='short'),'raw_timestamps':np.zeros((rawLength*10,),dtype='uint32'),'cerebusAdapter_time':np.zeros((rawLength*10,),dtype='uint32'),'udp_received_time':np.zeros((rawLength*10,),dtype='uint32')}

# filtered data
print('--------------------------------')
print('converting filtered data')
pageNum = 0
indStart = 0
for a in range(0,10):
   try:
      for xreadPack in r.xread({'filteredCerebusAdapter':readLocn_filt}, count=pageSize, block=None)[0][1]:
         indEnd = indStart + 30
         filt_dict['filt_samples'][:,indStart:indEnd] = np.reshape(unpack('h'*96*30,xreadPack[1][b'samples']),(96,30))
         filt_dict['filt_timestamps'][indStart:indEnd] = np.array(unpack('I'*30,xreadPack[1][b'sampleTimes']))
         readLocn_filt = xreadPack[0]
         indStart = indEnd
   except:
      break 
   pageNum += 1

print('saving  file')
#print('Size of sample dict:',getsizeof(filt_dict['filt_samples']))
#print('Size of timestamps dict:',getsizeof(filt_dict['filt_timestamps']))
io.savemat(FN_filt,filt_dict,do_compression=True)




# threshold crossings
print('--------------------------------')
print('converting threshold data')
pageNum = 0
ind= 0
for a in range(0,10):
   for xreadPack in r.xread({'thresholdCrossings':readLocn_thresh}, count=pageSize, block=None)[0][1]:
      indStart,indEnd = ind*30,(ind+1)*30
      thresh_dict['thresh_samples'][:,indStart:indEnd] = np.reshape(unpack('h'*96*30,xreadPack[1][b'samples']),(96,30))
      thresh_dict['tsStart'][ind] = np.array(unpack('I',xreadPack[1][b'tsStart']))
      thresh_dict['tsStop'][ind] = np.array(unpack('I',xreadPack[1][b'tsStop']))
      thresh_dict['thresh_timestamps'][indStart:indEnd] = np.array(unpack('I'*30,xreadPack[1][b'sampleTimes']))
      readLocn_thresh = xreadPack[0]
      ind +=1
   pageNum += 1

print('saving  file')
io.savemat(FN_thresh,thresh_dict,do_compression=True)




# raw data
print('--------------------------------')
print('converting raw data')
pageNum = 0
indStart = 0
for a in range(0,30):
   for xreadPack in r.xread({'cerebusAdapter':readLocn_raw}, count=pageSize, block=None)[0][1]:
      indEnd = indStart + 10
      raw_dict['raw_samples'][:,indStart:indEnd] = np.reshape(unpack('h'*96*10,xreadPack[1][b'samples']),(96,10))
      raw_dict['raw_timestamps'][indStart:indEnd] = np.array(unpack('I'*10,xreadPack[1][b'timestamps']))
      cerebusAdapter_time = np.reshape(unpack('ll'*10,xreadPack[1][b'cerebusAdapter_time']),(10,2))
      udp_time = np.reshape(unpack('ll'*10,xreadPack[1][b'udp_received_time']),(10,2))
      for ii in range(0,10):
         raw_dict['cerebusAdapter_time'][indStart+ii] = cerebusAdapter_time[ii,0]*1000000 + cerebusAdapter_time[ii,1]
         raw_dict['udp_received_time'][indStart+ii] = udp_time[ii,0]*1000000 + udp_time[ii,1]
      readLocn_raw = xreadPack[0]
      indStart = indEnd
   pageNum += 1

print('saving  file')
io.savemat(FN_raw,raw_dict,do_compression=True)
