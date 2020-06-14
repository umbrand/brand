# Summarize the statistics of data collection for a SQL file
# David Brandman, June 2020

## Imports 

import pandas as pd
import numpy as np
import sqlite3
from sqlite3 import Error
import sys
import struct
import matplotlib.pyplot as plt
import pathlib

###############################################
## Defining the filename
###############################################

sql_filename = "../../run/cerebusTest.2020-06-13_19.28.56.sqlite3"
pagination_limit = 1000
output_folder = "../../run/sql/"

###############################################
## Loading the SQL table and preliminaries
###############################################

con = sqlite3.connect(sql_filename)

sqlStr = "SELECT COUNT(ID) FROM cerebusAdapter"
num_rows = con.execute(sqlStr).fetchone()[0]

###############################################
## Question 1: Plotting cerebus timestamp diffs
###############################################

# We begin by counting the number of rows
# struct's definition of Unsigned int32: I

offset = 0
timestamps = []
while offset < num_rows:
    sqlStr = "SELECT num_samples, timestamps FROM cerebusAdapter LIMIT {} OFFSET {}".format(pagination_limit, offset)
    rows = con.execute(sqlStr).fetchall()
    print(sqlStr)

    for row in rows:
        unpack_str = 'I' * row[0]
        t = struct.unpack(unpack_str, row[1])
        timestamps = np.append(timestamps, np.array(t))
        offset = offset + 1

fig = plt.figure()
title = pathlib.Path(sql_filename).name + "\n Stream: cerebusAdapter \n Diff of cerebus timestamps as entered into Redis \n Diffs > 10 are truncated to 10"

diffs = np.diff(timestamps)
diffs[diffs > 10] = 10

plt.plot(diffs, 'o', markersize=2)
plt.ylabel('Cerebus Timestamp diff (delta int32)', fontsize=12);
plt.xlabel('Cerbus timestamp ordered by Redis', fontsize=12);
plt.title(title)

plt.ylim(0, 11)


filename = output_folder + "cerebus_timestamp_diffs.png"
fig.savefig(filename)


###############################################
## Question 2: Plotting Redis timestamp diffs
###############################################

offset = 0
timestamps = []
while offset < num_rows:
    sqlStr = "SELECT ID  FROM cerebusAdapter LIMIT {} OFFSET {}".format(pagination_limit, offset)
    rows = con.execute(sqlStr).fetchall()
    print(sqlStr)

    for row in rows:
        id = row[0].split('-')[0]
        timestamps = np.append(timestamps, np.array(id, dtype='int'))
        offset = offset + 1

fig = plt.figure()
title = pathlib.Path(sql_filename).name + "\n Stream: cerebusAdapter \n Diff of redis timestamps"

plt.plot(np.diff(timestamps), 'o', markersize=2)
plt.ylabel('Redis Timestamp diff', fontsize=12);
plt.xlabel('Redis entry', fontsize=12);
plt.title(title)

filename = output_folder + "redis_timestamp_diffs.png"
fig.savefig(filename)

###############################################
## Question 3: UDP packet interval
###############################################

offset = 0
timestamps = []
while offset < num_rows:
    sqlStr = "SELECT num_samples, udp_received_time FROM cerebusAdapter LIMIT {} OFFSET {}".format(pagination_limit, offset)
    rows = con.execute(sqlStr).fetchall()
    print(sqlStr)

    for row in rows:
        t = struct.unpack('ll'*row[0], row[1])
        microseconds = [t[x] * 1000000 + t[x+1] for x in range(0,len(t),2)]
        microseconds = np.unique(microseconds)
        print(microseconds)

        timestamps = np.append(timestamps, np.array(microseconds, dtype='int'))
        offset = offset + 1

fig = plt.figure()
title = pathlib.Path(sql_filename).name + "\n Stream: cerebusAdapter \n Diff of UDP received timestamps"

plt.plot(np.diff(timestamps), 'o', markersize=2)
plt.ylabel('UDP timestamp diff (microseconds)', fontsize=12);
plt.xlabel('Cerebus packet number', fontsize=12);
plt.title(title)

filename = output_folder + "udp_timestamp_diffs.png"
fig.savefig(filename)

###############################################
## Question 4: Cycle runtime
###############################################

offset = 0
timestamps = []
while offset < num_rows:
    sqlStr = "SELECT num_samples, current_time FROM cerebusAdapter LIMIT {} OFFSET {}".format(pagination_limit, offset)
    rows = con.execute(sqlStr).fetchall()
    print(sqlStr)

    for row in rows:
        t = struct.unpack('ll'*row[0], row[1])
        microseconds = [t[x] * 1000000 + t[x+1] for x in range(0,len(t),2)]
        timestamps = np.append(timestamps, np.array(microseconds, dtype='int'))
        offset = offset + 1

fig = plt.figure()
title = pathlib.Path(sql_filename).name + "\n Stream: cerebusAdapter \n Diff of cerebusAdapter gettimeofday calls"

plt.plot(np.diff(timestamps), 'o', markersize=2)
plt.ylabel('cerebusAdapter runtime diff (microseconds)', fontsize=12);
plt.xlabel('Cerebus packet number', fontsize=12);
plt.title(title)

filename = output_folder + "current_time_timestamp_diffs.png"
fig.savefig(filename)
