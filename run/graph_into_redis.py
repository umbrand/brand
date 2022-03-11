#!/usr/bin/env python
'''
graph_to_redis.py

this function is meant to be given a path to a graph yaml file.
It will then take the yaml file, parse it, and place it in the 
associated Redis instance so that all of the settings can be 
read by the associated nodes and stored in the same place for later on.


Kevin Bodkin
February 2022
'''


# import all of the relevent functions
from redis import redis
import argparse
from brand import *



# This is meant to be run as a script with the yaml filepath as the only argument
# pulling in argparse
if __name__ == '__main__':
    argDesc = """
            this function is meant to be given a path to a graph yaml file.
            It will then take the yaml file, parse it, and place it in the 
            associated Redis instance so that all of the settings can be 
            read by the associated nodes and stored in the same place for later on. """

    parser = argparse.ArgumentParser(description=argDesc)
    parser.add_argument("yaml", help="path to graph YAML settings file")
    args = parser.parse_args()
    graphYAML = arg.yaml


# initialize a Redis object

r = initializeRedisFromYAML(graphYAML, 'graph_into_redis')


# Get each piece of relevant data from the YAML file





            
