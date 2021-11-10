#!/usr/bin/env python
# -*- coding: utf-8 -*-
# beep.py


"""
beep.py

beeps at different frequencies depending on the state of the task.

@author: Kevin Human Primate
"""

import signal, os, sys
from redis import Redis
import argparse, pygame
from brand import *

nodeName = 'beep'


#############################################################
## defining helper functions
##########################################################'''

# signal handler for clean exits
def signal_handler(sig,frame): # setup the clean exit code with a warning
    print(f'[{nodeName}] SIGINT received, Exiting')
    sys.exit(0)

# place the sigint signal handler
signal.signal(signal.SIGINT, signal_handler)



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



#############################################################################
### Import settings from the .yaml, connect to Redis
#############################################################################
nodeParameters = get_node_parameter_dump(graphYAML, nodeName) # pull back a dictionary

print(f"[{nodeName}] initializing targets and cursors")

redis_io = get_node_io(graphYAML, nodeName)
inStreamName = list(redis_io['redis_inputs'].keys())[0] # getting the name of the state stream. If we get more than one, we're in trouble!

# connect to redis, figure out the streams of interest
try:
    r = initializeRedisFromYAML(graphYAML, nodeName)
except:
    print(f"[{nodeName}] Failed to connect to Redis. Exiting.")
    sys.exit()

pygame.mixer.init(frequency=48000, buffer=32000) # mister
goSound = pygame.mixer.Sound(nodeParameters['goSound'])
rewardSound = pygame.mixer.Sound(nodeParameters['rewardSound'])
failureSound = pygame.mixer.Sound(nodeParameters['failureSound'])


#############################################################################
### Main loop
#############################################################################


while True:
    state = r.xread({inStreamName:'$'}, count=1, block=500)#[0][1][b'state']
    
    if len(state) > 0:
        state = state[0][1][0][1][b'state']
        print(f"State is: {state}")
        if state == b'movement':
            goSound.play()
    
        elif state == b'reward':
            rewardSound.play()
    
        elif state == b'failure':
            failureSound.play()
    







