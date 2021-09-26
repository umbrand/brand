
## Imports
import pandas as pd
import numpy as np
import sys
import struct
import matplotlib.pyplot as plt
import pathlib
import redis
from matplotlib.animation import FuncAnimation, TimedAnimation


#########################################
## Initialize our relevant variables
#########################################

r = redis.Redis()
key = b'chan0'
box_width = 30000
box_advance = 1000






#########################################
## Load data from memory
#########################################

samples = []
timestamps = []

rows = r.xrange('continuousNeural', count=10000)
for row in rows:
    t = struct.unpack('h'*int(row[1][b'num_samples']), row[1][key])
    samples = np.append(samples, np.array(t, dtype='int'))

    t = struct.unpack('I' * int(row[1][b'num_samples']), row[1][b'timestamps'])
    timestamps = np.append(timestamps, np.array(t, dtype='uint32'))

#########################################
## Plotting function
#########################################
def updatePlot(i, *fargs): 

    if i*box_advance + box_width > len(timestamps):
        return

    ind = range(i*box_advance,i*box_advance+box_width)

    plt.cla()
    plt.scatter(x=timestamps[ind], y=samples[ind], s=3)
    # plt.ylim((-200,200))
    # plt.ylim((0,2000))

#########################################
## Show animation
#########################################

fig, ax = plt.subplots()
ani = FuncAnimation(plt.gcf(), updatePlot, fargs=(timestamps,samples), interval=100)
plt.show()
#move()

# def move():
#     mngr = plt.get_current_fig_manager()
#     mngr.window.setGeometry(1000,100,640, 545)
