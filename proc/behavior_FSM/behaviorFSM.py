# -*- coding: utf-8 -*-
"""
behaviorFSM.py

Keeps track of the behavioral state machine. This will take the 
inputs from whatever input we want, take care of the necessary gains
and offsets, keep track of the current cursor and target(s) and 
send all of that appropriate information to the Redis stream for the 
graphics controller.

 

@author: Kevin Human Primate
"""

import signal, os, sys
import numpy as np
from redis import Redis
from datetime import datetime as dt
from time import sleep


sys.path.insert(1,'../lib/redisTools/')
from redisTools import get_parameter_value
behavior_yaml = 'behaviorFSM.yaml'


'''##########################################################
## setting up clean exit code
##########################################################'''
def signal_handler(sig,frame): # setup the clean exit code with a warning
    print('[behaviorFSM] SIGINT received, Exiting')
    sys.exit(0)
    
signal.signal(signal.SIGINT, signal_handler) # place the handler




'''##########################################################
### defining the cursors, targets etc
##########################################################'''

### define target 
class target():
    # one instance for each target -- with a state to say whether the target is 
    # off, on, or if the cursor is over the target
    
    def __init__(self,tgtDict): # initialize the class
        self.location = {}
        self.location['state'] = 'off' # always start with everything off
        self.location['x'] = tgtDict['x']
        self.location['y'] = tgtDict['y']
        self.location['width'] = tgtDict['width']
        self.location['height'] = tgtDict['height']
        
    def off(self): # to turn the state 'off'
        self.state = 'off'
        
    def on(self): # to turn the state to 'on'
        self.state = 'on'
    
    def over(self):
        self.state = 'over' # to turn the state to 'over'
       
    def isOver(self, cursRect):
        self.color = 'on'
        # insert some sort of collision detection here
        return False



# define the cursor
class cursor:
    # probably just going to be the one instance
    
    # initialize
    def __init__(self,cursDict):
        self.mX = cursDict['x_offset']
        self.mY = cursDict['y_offset']
        self.bX0 = cursDict('gain_x_0')
        self.bX1 = cursDict('gain_x_1')
        self.bY0 = cursDict('gain_y_0')
        self.bY1 = cursDict('gain_y_1')
        # width and height are just for the collision bounding box
        self.'width' = cursDict['width'] 
        self.'height' = cursDict['height']
        # putting location and on/off info into a dictionary for easy
        # transfer into Redis. Using byte-strings for easier usage in C
        self.location = {}
        self.location[b'state'] = 'off' # always start with everything off
        self.location[b'x'] = 0 # just initialization
        self.location[b'y'] = 0

    def off(self):
        self.state = 'off'
        
    def on(self):
        self.state = 'on'
    
    def update_cursor(self, redisStream, sensor0, sensor1):
        redisFrame = redisStream.xread({'nidaq_stream','$'}, block=0, count=1)[0][1][0][1]
        
        if len(redisFrame) != 0:
            self.location['x'] = (redisFrame[sensor0]*self.mX0) + (redisFrame[sensor1]*self.mX1) + self.bX
            self.location['y'] = (redisFrame[sensor0]*self.mY0) + (redisFrame[sensor1]*self.mY1) + self.bY
    
    def recenter(self):
        self.bX = -self.x
        self.bY = -self.y


# storing timing info for between tasks, hold times etc
class delayGenerator():
    def __init__(self,inDict):
        self.min = inDict['min']
        self.max = inDict['max']
        self.current = (np.random.random() * (self.max-self.min)) + self.min
        
    def reroll(self):
        self.current = (np.random.random() * (self.max-self.min)) + self.min


def restart_task(targets):
    return targets[np.random.choice(list(targets.keys()))]

""" ##########################################################################
### Import settings from the .yaml, setup constants/global variables
###########################################################################"""

# targets
targets = {} # a list to hold all of the targets
for keys,values in get_parameter_value(behavior_yaml,'targetList').items():
    targets[keys] = target(values)

# cursor location
curs = cursor(get_parameter_value(behavior_yaml,'cursor'))


# initialize wait times
targetHoldTime = delayGenerator(get_parameter_value(behavior_yaml,'targetHoldTime')) # how long do they have to hold the target?
dispenseTime = delayGenerator(get_parameter_value(behavior_yaml,'dispenseTime')) # time to receive the reward
interTrialTime = delayGenerator(get_parameter_value(behavior_yaml,'interTrialTime')) # time between trials


# connect to redis, figure out the streams of interest
try:
    redis_ip = get_parameter_value(behavior_yaml,'redis_ip')
    redis_port = get_parameter_value(threshold_yaml,'redis_port')
    r = Redis(host = redis_ip, port = redis_port)
    print('[behaviorFSM] Connecting to Redis...')
except:
    print('[behaviorFSM] Failed to connect to Redis. Exiting.')
    sys.exit()


# state initialization
STATE_START_TRIAL = 0
STATE_MOVEMENT = 1
STATE_REWARD = 2
STATE_BETWEEN_TRIALS = 3

state = STATE_BETWEEN_TRIALS

'''##########################################################
### main loop
##########################################################'''

while True:
    
    # update the current location of the cursor
    curs.update_cursor(r, sensor0, sensor1) # sensor names
    
    if state == STATE_START_TRIAL:
        
    
    if state = STATE_MOVEMENT:
        
    
    if state = STATE_REWARD:
        
    
    if state = STATE_BETWEEEN_TRIALS:
        
    
    p = r.pipeline()
    p.xadd('cursorLocation', curs.location)
    p.xadd('targetLocation', tgtDict)
    p.execute()

