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
            self.over
            return True
        else:
            self.on
            return False
    
    def packTarget(self):
        return pack('Ihhhh',self.state,self.x,self.y,self.width,self.height)


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
    
    def update_cursor(self, nidaqStream, sensor0, sensor1):
        s0,s1 = unpack('h',nidaqStream[sensor0]),unpack('h',nidaqStream[sensor1])
        self.x = (s0*self.mX0) + (s1*self.mX1) + self.bX
        self.y = (s0*self.mY0) + (s1*self.mY1) + self.bY
    
    def recenter(self, nidaqStream, sensor0, sensor1):
        self.update_cursor(nidaqStream,sensor0,sensor1)
        self.bX = -self.x
        self.bY = -self.y
        self.update_cursor(nidaqStream, sensor0, sensor1)
    
    def packCurs(self):
        return pack('Ihh',self.state,self.x,self.y)


# define the touchpad
class touchpad():
    def __init__(self,minTouch,maxTouch):
        self.active = False
        self.tapped = False
        self.minTouch,self.maxTouch = minTouch,maxTouch
        self.touchStart = 0
    
    def activate(self,nidaqControl,redisPipe):
        self.active = True
        self.touchLength = (self.maxTouch-self.minTouch)*np.random.random() + self.minTouch
        self.touchStart = 0
        nidaqControl[b'touch_active'] = pack('?',1)
        redisPipe.add(b'nidaqControl',nidaqControl)
        
    
    def deactivate(self,nidaqControl,redisPipe):
        self.active = False
        nidaqControl[b'touch_active'] = pack('?',0)
        redisPipe.add(b'nidaqControl',nidaqControl)
    
    def tap_check(self,nidaqStream):
        if unpack('?',nidaqStream[b'touchpad_touched']):
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
stateTime = 0
nidaqControl = {b'touch_active':pack('?',0), b'reward':pack('?',0)}
'''##########################################################
### main loop
##########################################################'''

while True:
    
    # update the current location of the cursor
    nidaqFrame = redisStream.xread({b'nidaq_stream','$'}, block=0, count=1)[0][1][0][1]
    curs.update_cursor(nidaqFrame, sensor0, sensor1) # sensor names
    currTime = dt.now().timestamp() # the posix time at the beginning of the loop
    p = r.pipeline()
    p.xadd(b'cursorLocation',curs.packCurs)
    p.xadd(b'targetLocation',tgt.packTarget)
    
    if state == STATE_START_TRIAL:
        if tpad.tap_check(nidaqFrame):
            p.xadd(b'state',{b'state': b'movement', b'time': currTime})
            state = STATE_MOVEMENT
            stateTime = 0
            tPad.deactivate(nidaqControl,p)
    
    if state == STATE_MOVEMENT:
        if tgt.isOver(curs):
            if stateTime == 0:
                stateTime = currTime
            elif (dt.now().timestamp() - inTgtTime) > :targetHoldTime
                state = STATE_REWARD # next state
                p.xadd(b'state',{b'state':b'movement', b'time': currTime})
                tgt.off()
                curs.off()
                stateTime = currTime
        
        else: 
            stateTime = 0 # reset the time over the target
            
            
    
    if state == STATE_REWARD:
        nidaqControl[b'reward'] == pack('?',True)
        if (currTime-stateTime) > dispenseTime:
            state = STATE_BETWEEN_TRIALS
            p.xadd(b'state',{b'state':b'movement',b'time',currTime})
            nidaqControl[b'reward'] = pack('?',False)
            stateTime = currTime
        
        p.add(b'nidaqControl',nidaqControl)
    
    if state == STATE_BETWEEEN_TRIALS:
        if (currTime-stateTime) > interTrialTime:
            tgt = restart_task(targets)
            tPad.activate(nidaqControl,p)
            targetHoldTime.reroll()
            dispenseTime.reroll()
            interTrialTime.reroll()
            p.xadd(b'state',{b'state':'start_trial',b'time':currTime})
            state = STATE_START_TRIAL
    
    
    p.execute()

