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
from time import sleep
from struct import pack, unpack

# check to see if we're trying to run this from the base directory or from inside of 'run'
# for debugging purposes when I'm jumping between files a lot
if os.getcwd().split('/')[-1] == 'realtime_rig_dev':
    sys.path.insert(1,'lib/redisTools/')
else: # assumes we're only one directory below the base
    sys.path.insert(1,'../lib/redisTools/')
from redisTools import get_parameter_value
behavior_yaml = 'behaviorFSM.yaml'


'''##########################################################
## setting up clean exit code
##########################################################'''
def signal_handler(sig,frame): # setup the clean exit code with a warning
    print('[behaviorFSM] SIGINT received, Exiting')
    sys.exit(0)

# place the sigint signal handler    
signal.signal(signal.SIGINT, signal_handler) 




'''##########################################################
### defining the cursors, targets etc
##########################################################'''

### define target 
class target():
    # one instance for each target -- with a state to say whether the target is 
    # off, on, or if the cursor is over the target
    
    def __init__(self,tgtDict): # initialize the class
        self.state = 0 # always start with everything off
        self.x = tgtDict['x']
        self.y = tgtDict['y']
        self.width = tgtDict['width']
        self.height = tgtDict['height']
        
    def off(self): # to turn the state 'off'
        self.state = 0
        
    def on(self): # to turn the state to 'on'
        self.state = 1
    
    def over(self):
        self.state = 2 # to turn the state to 'over'
       
    def isOver(self, curs):
        self.on
        x = self.x - curs.x # center everything on the target
        y = self.y - curs.y
        # if the cursor is within the target's range
        if (abs(x) <= self.width/2) and (abs(y) <= self.height/2):
            self.over()
            return True
        else:
            return False
    
    def packTarget(self):
        targetDict = {b'X': pack('i',self.x), b'Y': pack('i',self.y), b'width': pack('i',self.width), b'height': pack('i',self.height), b'state':pack('I',self.state)}
        return targetDict


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
    
    def packCurs(self):
        cursorDict = {b'X': pack('i', int(self.x)), b'Y': pack('i',int(self.y)), b'state': pack('I',int(self.state))}
        return cursorDict

    def printCurs(self):
        print("X: "+ str(curs.x) + ", Y: " + str(curs.y))


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
        print(sensor-self.thresh);
        if sensor > self.thresh:
            if self.touchStart == 0:
                self.touchStart = dt.now().timestamp()
                return False
            elif (dt.now().timestamp() - self.touchStart) > self.touchLength:
                return True
        else:
            self.touchStart = 0
            return False


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
print('[behaviorFSM] initializing targets and cursors')
# targets
targets = {} # a list to hold all of the targets
for keys,values in get_parameter_value(behavior_yaml,'targetList').items(): # load in all of the targets
    targets[keys] = target(values)
tgt = restart_task(targets) # pick a target to start

# cursor location
curs = cursor(get_parameter_value(behavior_yaml,'cursor'))


# initialize wait times
targetHoldTime = delayGenerator(get_parameter_value(behavior_yaml,'targetHoldTime')) # how long do they have to hold the target?
dispenseTime = delayGenerator(get_parameter_value(behavior_yaml,'dispenseTime')) # time to receive the reward
interTrialTime = delayGenerator(get_parameter_value(behavior_yaml,'interTrialTime')) # time between trials
touchpadTime = get_parameter_value(behavior_yaml,'touchpadTime') # touchpad min, max

# initialize sensor settings
unpackString = get_parameter_value(behavior_yaml,'unpackString')
cursorSensors = get_parameter_value(behavior_yaml,'cursorSensors')
touchpadSensor = get_parameter_value(behavior_yaml, 'touchpadSensor')
touchpadThresh = get_parameter_value(behavior_yaml, 'touchpadThresh')

# connect to redis, figure out the streams of interest
try:
    redis_ip = get_parameter_value(behavior_yaml,'redis_ip')
    redis_port = get_parameter_value(behavior_yaml,'redis_port')
    print('[behaviorFSM] Redis IP', redis_ip, ';  Redis port:', redis_port)
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
stateTime = 0
behaviorControl = {b'touch_active':pack('?',0), b'reward':pack('?',0)}
tPad = touchpad(touchpadTime['min'],touchpadTime['max'],touchpadThresh)
'''##########################################################
### main loop
##########################################################'''

while True:
    
    # update the current location of the cursor
    cursorFrame = r.xread({b'cerebusAdapter_task':'$'}, block=10, count=1)[0][1][0][1]
    sensors = unpack(unpackString, cursorFrame[b'samples']) # pulling a sensor in
    sensor0,sensor1 = sensors[0:2]
    sensor2 = sensors[2]
    curs.update_cursor(sensor0, sensor1) # sensor names
    currTime = dt.now().timestamp() # the posix time at the beginning of the loop
    p = r.pipeline()
    p.xadd(b'cursorData',curs.packCurs())
    p.xadd(b'targetData',tgt.packTarget())
    
    if state == STATE_START_TRIAL:
        if tPad.tap_check(sensor2):
            p.xadd(b'state',{b'state': b'movement', b'time': currTime})
            tgt.on()
            state = STATE_MOVEMENT
            stateTime = 0
            tPad.deactivate(behaviorControl, p)
    
    if state == STATE_MOVEMENT:
        if tgt.isOver(curs):
            if stateTime == 0:
                stateTime = currTime
            elif (dt.now().timestamp() - stateTime) > targetHoldTime.current:
                state = STATE_REWARD # next state
                p.xadd(b'state',{b'state':b'movement', b'time': currTime})
                tgt.off()
                curs.off()
                stateTime = currTime
        
        else: 
            stateTime = 0 # reset the time over the target
            
            
    
    if state == STATE_REWARD:
        behaviorControl[b'reward'] = pack('?',True)
        if stateTime == 0:
            stateTime = currTime;
        if (currTime-stateTime) > dispenseTime.current:
            state = STATE_BETWEEN_TRIALS
            p.xadd(b'state',{b'state':b'movement',b'time':currTime})
            behaviorControl[b'reward'] = pack('?',False)
            stateTime = currTime
        
        p.xadd(b'behaviorControl',behaviorControl)
    
    if state == STATE_BETWEEN_TRIALS:
        if (currTime-stateTime) > interTrialTime.current:
            tgt = restart_task(targets)
            tPad.activate(behaviorControl,p)
            targetHoldTime.reroll()
            dispenseTime.reroll()
            interTrialTime.reroll()
            p.xadd(b'state',{b'state':'start_trial',b'time':currTime})
            state = STATE_START_TRIAL
    
    
    p.execute()

