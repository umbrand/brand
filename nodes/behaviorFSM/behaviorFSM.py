#!/usr/bin/env python
# -*- coding: utf-8 -*-
# behaviorFSM.py


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
from time import sleep, perf_counter
from struct import pack, unpack
import argparse
from brand import *
behavior_yaml = 'behaviorFSM.yaml'
graphYAML = ''
nodeName = 'behaviorFSM'


#############################################################
## setting up clean exit code
#############################################################
def signal_handler(sig,frame): # setup the clean exit code with a warning
    print('[behaviorFSM] SIGINT received, Exiting')
    sys.exit(0)

# place the sigint signal handler    
signal.signal(signal.SIGINT, signal_handler) 




#############################################################
### defining the cursors, targets etc
#############################################################

### define target 
class target():
    # one instance for each target -- with a state to say whether the target is 
    # off, on, or if the cursor is over the target
    
    def __init__(self,tgtDict): # initialize the class
        self.state = 0 # always start with everything off
        self.x = tgtDict['x']
        self.y = tgtDict['y']
        self.targetTime = None
        self.targetHoldTime = None
        self.width = tgtDict['width']
        self.height = tgtDict['height']
        
    def off(self): # to turn the state 'off'
        self.targetTime = None
        self.state = 0
        
    def on(self, targetHoldTime = None): # to turn the state to 'on'
        if targetHoldTime is not None:
            self.targetHoldTime = targetHoldTime
        self.targetTime = None
        self.state = 1
    
    def over(self):
        self.state = 2 # to turn the state to 'over'
       
    def isOver(self, curs, tCurr):
        self.on
        x = self.x - curs.x # center everything on the target
        y = self.y - curs.y
        # if the cursor is within the target's range
        if (abs(x) <= self.width/2) and (abs(y) <= self.height/2):
            self.over()
            if self.targetTime is None:
                self.targetTime = tCurr
                return False
            elif (tCurr - self.targetTime) > self.targetHoldTime:
                self.off()
                return True
        else:
            self.on()
            return False
    
    def packTarget(self, sync):
        # sync is the value of the cerebus timestamps associated with the 
        # sample data stream that originally results in these values
        targetDict = {b'X': pack('i',self.x), b'Y': pack('i',self.y), b'width': pack('i',self.width), b'height': pack('i',self.height), b'state':pack('I',self.state), b'sync': sync}
        return targetDict

# --------------------------------------------------------------------
# define the cursor
class cursor:
    # probably just going to be the one instance
    
    # initialize
    def __init__(self,cursDict):
        self.bX = cursDict['x_offset']
        self.bY = cursDict['y_offset']
        self.mX0 = cursDict['gain_x_0']
        self.mX1 = cursDict['gain_x_1']
        self.mY0 = cursDict['gain_y_0']
        self.mY1 = cursDict['gain_y_1']
        # width and height are just for the collision bounding box -- ignore for now
        self.width = cursDict['width'] 
        self.height = cursDict['height']
        # we'll pack the three output values (state, x and y)
        # into a single byte string later to send to redis
        self.state = 0 # always start with everything off
        self.x = 0 # just initialization
        self.y = 0

    def off(self):
        self.state = 0
        
    def on(self):
        self.state = 1
    
    def update_cursor(self, s0, s1):
        self.x = -(-(s0*self.mX0) + (s1*self.mX1) + self.bX)
        self.y = -((s0*self.mY0) + (s1*self.mY1) + self.bY)
    
    def recenter(self, sensor0, sensor1):
        self.update_cursor(sensor0, sensor1)
        self.bX = -self.x
        self.bY = -self.y
        self.update_cursor(sensor0, sensor1)
    
    def packCurs(self, sync):
        # sync is the value of the cerebus timestamps associated with the 
        # sample data stream that originally results in these values
        cursorDict = {b'X': pack('i', int(self.x)), b'Y': pack('i',int(self.y)), b'state': pack('I',self.state), b'sync': sync}
        return cursorDict

    def printCurs(self):
        print(f"X:{self.x:3.2f}  Y:{self.y:3.2f}  state:{self.state}")

# --------------------------------------------------------------------
# define the touchpad
class touchpad():
    def __init__(self, minTouch, maxTouch, threshold):
        self.active = False
        self.tapped = False
        self.thresh = threshold
        self.minTouch,self.maxTouch = minTouch,maxTouch
        self.touchStart = 0
    
    def activate(self, bControl, redisPipe):
        self.active = True
        self.touchLength = (self.maxTouch-self.minTouch)*np.random.random() + self.minTouch
        self.touchStart = 0
        bControl[b'touch_active'] = pack('?',1)
        redisPipe.xadd(b'behaviorControl', bControl)
        
    
    def deactivate(self, bControl, redisPipe):
        self.active = False
        bControl[b'touch_active'] = pack('?',0)
        redisPipe.xadd(b'behaviorControl', bControl)
    
    def tap_check(self, sensor):
        # print(sensor-self.thresh);
        if sensor > self.thresh:
            if self.touchStart == 0:
                self.touchStart = dt.now().timestamp()
                return False
            elif (dt.now().timestamp() - self.touchStart) > self.touchLength:
                return True
        else:
            self.touchStart = 0
            return False

# defining the state machine in an object-oriented way
# -------------------------------------------------------------
#class state_machine():
#    def __init__():
#        # initialize rewards and counters
#        self.loopTimer = 0
#        self.stateTimer = 0
#        self.loopCounter = 0
#        self.rewardCounter = 0
#        self.failCounter = 0
#        self.abortCounter = 0
#        
#        self.State = NULL
#        
#    def addState:







# --------------------------------------------------------------------
# storing timing info for between tasks, hold times etc
class delayGenerator():
    def __init__(self,inDict):
        self.min = inDict['min']
        self.max = inDict['max']
        self.current = (np.random.random() * (self.max-self.min)) + self.min
        
    def reroll(self):
        self.current = (np.random.random() * (self.max-self.min)) + self.min

# --------------------------------------------------------------------
def restart_task(targets):
    return targets[np.random.choice(list(targets.keys()))]



# --------------------------------------------------------------------
# argparser for bringing in command line arguments
if __name__ == '__main__':
    description = '''
        Keeps track of the behavioral state machine. This will take the 
        inputs from whatever input we want, take care of the necessary gains
        and offsets, keep track of the current cursor and target(s) and 
        send all of that appropriate information to the Redis stream for the 
        graphics controller.
        '''

    parser = argparse.ArgumentParser(description = description)
    parser.add_argument('yaml', help="path to graph YAML settings file")
    args = parser.parse_args()
    graphYAML = args.yaml # yaml file


""" ##########################################################################
### Import settings from the .yaml, setup constants/global variables
###########################################################################"""
nodeParameters = get_node_parameter_dump(graphYAML, nodeName) # pull back a dictionary

print('[behaviorFSM] initializing targets and cursors')

# cursor location
curs = cursor(nodeParameters['cursor']) # create a cursor object


# initialize wait times
targetHoldTime = delayGenerator(nodeParameters['target_hold_time'])# how long do they have to hold the target?
dispenseTime = delayGenerator(nodeParameters['dispense_time']) # time to receive the reward
interTrialTime = delayGenerator(nodeParameters['inter_trial_time']) # time between trials
touchpadTime = nodeParameters['touchpad_time'] # touchpad min, max
movement_max_time = nodeParameters['movement_max_time'] # maximum amount of time the movement process can take

# targets
targets = {} # a list to hold all of the targets
for keys,values in nodeParameters['target_list'].items(): # load in all of the targets
    targets[keys] = target(values)
tgt = restart_task(targets) # pick a target to start

# initialize sensor settings
cursorSensors = nodeParameters['cursor_sensors'] # cursor sensor channel #s
touchpadSensor = nodeParameters['touchpad_sensor'] # touchpad sensor channel #
touchpadThresh = nodeParameters['touchpad_thresh'] # value of touchpad voltage when touched

# get info about the redis input/outputs
redis_io = get_node_io(graphYAML, nodeName)
inStreamName = list(redis_io['redis_inputs'].keys())[0] # getting out the name of the stream. If there's more than one io then we're in trouble!
unpackString = unpack_string(graphYAML, inStreamName)


# connect to redis, figure out the streams of interest
try:
    r = initializeRedisFromYAML(graphYAML, nodeName)
except:
    print(f"[{nodeName}] Failed to connect to Redis. Exiting.")
    sys.exit()


# state initialization
STATE_START_TRIAL = 0
STATE_MOVEMENT = 1
STATE_REWARD = 2
STATE_BETWEEN_TRIALS = 3
STATE_FAILURE = 4

state = STATE_BETWEEN_TRIALS
stateTime = 0
behaviorControl = {b'touch_active':pack('?',0), b'reward':pack('?',0)}
tPad = touchpad(touchpadTime['min'],touchpadTime['max'],touchpadThresh)
'''##########################################################
### main loop
##########################################################'''


tCurrent, tElapsed = perf_counter(), 0
emptyLoopCounter = 0

while True:
    # make sure each loop is 5 ms
    while (perf_counter() - tCurrent) < .002:
        sleep(.00001)

    # update the current location of the cursor
    tCurrent = perf_counter() # for timing the loop
    cursorFrame = r.xrevrange(inStreamName, count=1)
    if len(cursorFrame) > 0:
        emptyLoopCounter = 0

        sensors = unpack(unpackString, cursorFrame[0][1][b'samples']) # pulling a sensor in
        sensor0,sensor1 = sensors[1:3]
        sensTouch = sensors[0]
        curs.update_cursor(sensor0, sensor1) # sensor names
        #curs.printCurs()
        currTimestamp = dt.now().timestamp() # for sample timestamps
        p = r.pipeline()
        p.xadd(b'cursorData',curs.packCurs(cursorFrame[0][1][b'timestamps']))
        p.xadd(b'targetData',tgt.packTarget(cursorFrame[0][1][b'timestamps']))
        
        if state == STATE_START_TRIAL:
            if tPad.tap_check(sensTouch):
                p.xadd(b'state',{b'state': b'movement', b'time': currTimestamp, b'sync': cursorFrame[0][1][b'timestamps']})
                tgt.on(targetHoldTime.current)
                curs.on()
                state = STATE_MOVEMENT
                stateTime = tCurrent # keeping track of how long we're in a specific state -- for movement timeout
                tPad.deactivate(behaviorControl, p)
        
    
        if state == STATE_MOVEMENT:
            if (tCurrent - stateTime) <= movement_max_time:
                if tgt.isOver(curs, tCurrent): # if the cursor has been over the target for more than X amount of time
                    state = STATE_REWARD # next state
                    p.xadd(b'state',{b'state':b'reward', b'time': currTimestamp, b'sync': cursorFrame[0][1][b'timestamps']})
                    curs.off()
                    stateTime = tCurrent
            else:
                state = STATE_FAILURE
                stateTime = tCurrent
                tgt.off()
                curs.off()
                p.xadd(b'state',{b'state':b'failure', b'time': currTimestamp, b'sync': cursorFrame[0][1][b'timestamps']})
                
        
        if state == STATE_REWARD:
            behaviorControl[b'reward'] = pack('?',True)
            if (tCurrent-stateTime) > dispenseTime.current:
                state = STATE_BETWEEN_TRIALS
                p.xadd(b'state',{b'state':b'between_trials',b'time':currTimestamp, b'sync': cursorFrame[0][1][b'timestamps']})
                behaviorControl[b'reward'] = pack('?',False)
                stateTime = tCurrent
            
            p.xadd(b'behaviorControl',behaviorControl)
        
    
    
        if state == STATE_BETWEEN_TRIALS or state == STATE_FAILURE:
            if (tCurrent-stateTime) > interTrialTime.current:
                tgt = restart_task(targets)
                tPad.activate(behaviorControl,p)
                targetHoldTime.reroll()
                dispenseTime.reroll()
                interTrialTime.reroll()
                p.xadd(b'state',{b'state':'start_trial',b'time':currTimestamp, b'sync': cursorFrame[0][1][b'timestamps']})
                state = STATE_START_TRIAL
        
        
        p.execute()
    
    else:  
        emptyLoopCounter += 1
        if emptyLoopCounter > 500:
            emptyLoopCounter = 0
            print("No input data available in stream")



