# Summarize the statistics of data collection for a SQL file's monitor stream
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


sql_filename = "../run/current.sqlite3"
pagination_limit = 1000
output_folder = "../run/sql/"

###############################################
## Loading the SQL table and preliminaries
###############################################

con = sqlite3.connect(sql_filename)

sqlStr = "SELECT COUNT(ID) FROM monitor"
num_rows = con.execute(sqlStr).fetchone()[0]

###############################################
## Question 1: Inter-run interval for monitor process
###############################################

offset = 0
timestamps = []
while offset < num_rows:
    sqlStr = "SELECT monitor_time FROM monitor LIMIT {} OFFSET {}".format(pagination_limit, offset)
    rows = con.execute(sqlStr).fetchall()
    print(sqlStr)

    for row in rows:
        timestamps = np.append(timestamps, np.array(int(row[0])))
        offset = offset + 1

fig = plt.figure()
title = pathlib.Path(sql_filename).name + "\n Stream: monitor \n Diff of monitor runtimes \n Timer set to 1000 microseconds"

diffs = np.diff(timestamps)
plt.plot(diffs, 'o', markersize=2)
plt.ylabel('monitor runtime delta (microseconds)', fontsize=12);
plt.xlabel('Execution cycle', fontsize=12);
plt.title(title)

# plt.ylim(0, 11)


filename = output_folder + "monitor_runtime_diffs.png"
fig.savefig(filename)


###############################################
## Question 2: Plotting difference between cerebus timestamp and monitor timestamp
###############################################

offset = 0
monitor_timestamps = []
cerebus_timestamps = []

while offset < num_rows:
    sqlStr = "SELECT monitor_time, cerebus_timestamp FROM monitor LIMIT {} OFFSET {}".format(pagination_limit, offset)
    rows = con.execute(sqlStr).fetchall()
    print(sqlStr)

    for row in rows:
        monitor_timestamps = np.append(monitor_timestamps, np.array(int(row[0])))
        cerebus_timestamps = np.append(cerebus_timestamps, np.array(int(row[1])))
        offset = offset + 1

fig = plt.figure()
title = pathlib.Path(sql_filename).name + "\n Stream: monitor \n Diff of monitor runtime and last cerebus packet read during execution \n Timer set to 1000 microseconds"

monitor_timestamps = monitor_timestamps - monitor_timestamps[0]
cerebus_timestamps = cerebus_timestamps - cerebus_timestamps[0]
diffs = np.diff(monitor_timestamps - cerebus_timestamps)
plt.plot(diffs, 'o', markersize=2)
plt.ylabel('Delta monitor to cerebus timestamp (microsecs)', fontsize=12);
plt.xlabel('Execution cycle', fontsize=12);
plt.title(title)

# plt.ylim(-100, 100)


filename = output_folder + "monitor_timestamps_minus_cerebus_timestamps.png"
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
