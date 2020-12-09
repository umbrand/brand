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
        self.state = 'off' # always start with everything off
        self.x = tgtDict['x']
        self.y = tgtDict['y']
        self.width = tgtDict['width']
        self.height = tgtDict['height']
        
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
    def __init__(self,x,y,width,height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.state = 'off' # always start with everything off

    def off(self):
        self.state = 'off'
        
    def on(self):
        self.state = 'on'
    

""" ##########################################################################
### Import settings from the .yaml, setup constants/global variables
###########################################################################"""
targetList = get_parameter_value(behavior_yaml,'targetList')
targets = () # a list to hold all of the targets
for tgtDict in targetList:
    targets(:-1) = target(tgt)




