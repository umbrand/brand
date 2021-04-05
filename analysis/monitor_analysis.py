# Summarize the statistics of data collection for a SQL file's monitor stream
# David Brandman, June 2020

## Imports 

#telling matplotlib to us Agg so that we can run this without using X
import os
headless = 'DISPLAY' not in os.environ
if headless:
	import matplotlib
	matplotlib.use("Agg")




import pandas as pd
import numpy as np
import sqlite3
from sqlite3 import Error
import sys
import struct
import matplotlib.pyplot as plt
import pathlib
import redis

###############################################
## Defining some important variables
###############################################

pagination_limit = 100000
output_folder = "./"

r = redis.Redis('165.124.111.117','6379')
num_rows = r.xinfo_stream('monitor')['length']

###############################################
## Pagination
###############################################

# stream -> string
# key -> string
# min_ID -> Binary string
# count -> Number
# Since there's no way to paginate with Redis, this is a little helper function 
def xrange_pagination(stream, min_ID, count):

    # If we're providing an ID, then increment the part after "-" by 1
    if min_ID != '-':
        split_last_id = min_ID.split(b'-')
        min_ID = split_last_id[0].decode('utf-8') + "-" + str(int(split_last_id[1])+1)

    return r.xrange(stream, min=min_ID, max='+', count=count)




# combined the two questions into one loop to make everything run a little smoother


###############################################
## Question 1: Inter-run interval for monitor process
###############################################

# Were're interested in looking at the difference between
# execution timestamps for the monitor process. This is straightforward



###############################################
## Question 2: Plotting difference between cerebus timestamp and monitor timestamp
###############################################

# We're interested in the question of jitter between when monitor runs
# (say, on a 1ms cycle) and when new data comes in through cerebusAdapter
# cerebus_timestamp contains the latest cerebus packet timestamp available when 
# monitor ran during its cycle. Since data is produced at 30Khz, we apply a 
# 1/30000 correction to the diffs between cb packet timestamps. Moreover, we do 
# our calculations in microseconds, so we add the *1e6 scaling factor

print("[monitor stream] Computing diff between monitor and cerebus timestamps")

offset = 0
monitor_timestamps = np.empty(num_rows)
cerebus_timestamps = np.empty(num_rows)
min_ID = '-'
while offset < num_rows:
    rows = xrange_pagination('monitor',min_ID, pagination_limit)

    for row in rows:
        monitor_timestamps[offset] = np.array((row[1][b'monitor_time']), dtype='uint64')
        cerebus_timestamps[offset] = np.array((row[1][b'cerebus_timestamp']), dtype='uint64')
        # monitor_timestamps = np.append(monitor_timestamps, np.array((row[1][b'monitor_time']), dtype='uint64'))
        # cerebus_timestamps = np.append(cerebus_timestamps, np.array((row[1][b'cerebus_timestamp']),dtype='uint64'))
        offset = offset + 1

    min_ID = rows[-1][0]
    print('[monitor stream]', offset, 'of', num_rows)



monitor_timestamps = monitor_timestamps - monitor_timestamps[0]
cerebus_timestamps = (cerebus_timestamps - cerebus_timestamps[0]) / 30000 * 1000000


fig = plt.figure()
title = "\n Stream: monitor \n Diff of monitor runtime and last cerebus packet read during execution \n Timer set to 1000 microseconds"

diffs = np.diff(monitor_timestamps - cerebus_timestamps) 
plt.plot(diffs, 'o', markersize=2)
plt.ylabel('Delta monitor to cerebus timestamp (us)', fontsize=12);
plt.xlabel('Execution cycle', fontsize=12);
plt.title(title)



filename = output_folder + "monitor_timestamps_minus_cerebus_timestamps.png"
fig.savefig(filename)


print('[monitor stream] Generating inter-run interval')


diffs = np.diff(monitor_timestamps)

fig = plt.figure()

title = "Stream: monitor \n Diff of monitor runtimes \n Timer set to 1000 microseconds"
plt.subplot(121)
plt.plot(diffs, 'o', markersize=2)
plt.ylabel('monitor runtime delta (us)', fontsize=12);
plt.xlabel('Execution cycle', fontsize=12);
plt.title(title)

title = "Histogram"
plt.subplot(122)
plt.hist(diffs, 50)
plt.ylabel('Count', fontsize=12);
plt.xlabel('Monitor runtime delta cycle', fontsize=12);
plt.title(title)


filename = output_folder + "monitor_runtime_diffs.png"
fig.savefig(filename)
