# Summarize the statistics of data collection for a SQL file
# David Brandman, June 2020

## Imports 

import pandas as pd
import numpy as np
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

r = redis.Redis()
num_rows = r.xinfo_stream('cerebusAdapter')['length']

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

###############################################
## Question 1: Plotting cerebus timestamp diffs
###############################################

# We begin by counting the number of rows
# struct's definition of Unsigned int32: I

print('[cerebusAdapter] Examining cerebus packet differences')

offset = 0
timestamps = []
min_ID = '-'
while offset < num_rows:
    rows = xrange_pagination('cerebusAdapter',min_ID, pagination_limit)

    for row in rows:
        t = struct.unpack('I' * int(row[1][b'num_samples']), row[1][b'timestamps'])
        timestamps = np.append(timestamps, np.array(t, dtype='uint32'))
        offset = offset + 1

    print('[cerebusAdapter stream]', offset, 'of', num_rows)

fig = plt.figure()
title = "Stream: cerebusAdapter \n Diff of cerebus timestamps as entered into Redis \n Diff changes > 10 are truncated to 10"

diffs = np.diff(timestamps)
diffs[diffs > 10] = 10
diffs[diffs < -10] = -10

plt.plot(diffs, 'o', markersize=2)
plt.ylabel('Cerebus Timestamp diff (delta int32)', fontsize=12);
plt.xlabel('Cerbus timestamp ordered by Redis', fontsize=12);
plt.title(title)

plt.ylim(0, 11)


filename = output_folder + "cerebus_timestamp_diffs.png"
fig.savefig(filename)


###############################################
## Question 2: UDP packet interval
###############################################

print('[cerebusAdapter] Examining UDP received interval')

offset = 0
timestamps = []
min_ID = '-'
while offset < num_rows:

    rows = xrange_pagination('cerebusAdapter',min_ID, pagination_limit)

    for row in rows:
        t = struct.unpack('ll'*int(row[1][b'num_samples']), row[1][b'udp_received_time'])
        microseconds = [t[x] * 1000000 + t[x+1] for x in range(0,len(t),2)]
        microseconds = np.unique(microseconds)

        timestamps = np.append(timestamps, np.array(microseconds, dtype='int'))
        offset = offset + 1

    print('[cerebusAdapter stream]', offset, 'of', num_rows)

fig = plt.figure()
title = "\n Stream: cerebusAdapter \n Diff of UDP received timestamps \n Diff changes > 2000us are truncated to 2000us"

diffs = np.diff(timestamps)
diffs[diffs > 2000] = 1000
diffs[diffs < -2000] = -1000

plt.plot(diffs, 'o', markersize=2)
plt.ylabel('UDP timestamp diff (microseconds)', fontsize=12);
plt.xlabel('Cerebus packet number', fontsize=12);
plt.title(title)

filename = output_folder + "cerebus_udp_timestamp_diffs.png"
fig.savefig(filename)



###############################################
#
#
#
# EXIT. Everything beyond here won't create new files
#
#
#
################################################


## Plot the actual samples to see what we're working with

num_cerebusAdapter_entries = 1000
key = b'chan0'
rows = r.xrevrange('cerebusAdapter', count=num_cerebusAdapter_entries)
samples = []

for row in rows:
    t = struct.unpack('h'*int(row[1][b'num_samples']), row[1][key])
    samples = np.append(samples, np.array(t, dtype='int'))



###############################################
## Question 4: Cycle runtime
###############################################

# offset = 0
# timestamps = []
# while offset < num_rows:
#     sqlStr = "SELECT num_samples, current_time FROM cerebusAdapter LIMIT {} OFFSET {}".format(pagination_limit, offset)
#     rows = con.execute(sqlStr).fetchall()

#     for row in rows:
#         t = struct.unpack('ll'*row[0], row[1])
#         microseconds = [t[x] * 1000000 + t[x+1] for x in range(0,len(t),2)]
#         timestamps = np.append(timestamps, np.array(microseconds, dtype='int'))
#         offset = offset + 1

# fig = plt.figure()
# title = pathlib.Path(sql_filename).name + "\n Stream: cerebusAdapter \n Diff of cerebusAdapter gettimeofday calls"

# plt.plot(np.diff(timestamps), 'o', markersize=2)
# plt.ylabel('cerebusAdapter runtime diff (microseconds)', fontsize=12);
# plt.xlabel('Cerebus packet number', fontsize=12);
# plt.title(title)

# filename = output_folder + "current_time_timestamp_diffs.png"
# fig.savefig(filename)

###############################################
## Question 2: Plotting Redis timestamp diffs
###############################################

# offset = 0
# timestamps = []
# min_ID = '-'
# while offset < num_rows:
#     sqlStr = "SELECT ID  FROM cerebusAdapter LIMIT {} OFFSET {}".format(pagination_limit, offset)
#     rows = con.execute(sqlStr).fetchall()
#     print(sqlStr)

#     for row in rows:
#         id = row[0].split('-')[0]
#         timestamps = np.append(timestamps, np.array(id, dtype='int'))
#         offset = offset + 1

# fig = plt.figure()
# title = pathlib.Path(sql_filename).name + "\n Stream: cerebusAdapter \n Diff of redis timestamps"

# plt.plot(np.diff(timestamps), 'o', markersize=2)
# plt.ylabel('Redis Timestamp diff', fontsize=12);
# plt.xlabel('Redis entry', fontsize=12);
# plt.title(title)

# filename = output_folder + "redis_timestamp_diffs.png"
# fig.savefig(filename)

