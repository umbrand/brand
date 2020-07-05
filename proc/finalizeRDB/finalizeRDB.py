#!/usr/bin/env python
# finalizeRDB.py
# When we're done with our session, we want to incorporate extra information to the RDB file
# David Brandman
# June 2020
 

import redis
import time
import datetime
import yaml
import sys

# Pathway to get redisTools.py
sys.path.insert(1, '../lib/redisTools/')
from redisTools import get_parameter_value

YAML_FILE = "finalizeRDB.yaml"

##########################################
## Helper function for working with Redis
##########################################
def redis_connect():

    redis_ip   = get_parameter_value(YAML_FILE,"redis_ip")
    redis_port = get_parameter_value(YAML_FILE,"redis_port")

    print("[finalizeRDB] Initializing Redis with IP :" , redis_ip, ", port: ", redis_port)
    r = redis.Redis(host = redis_ip, port = redis_port, db = 0)
    return r


##########################################
## Helper function for working with yaml
##########################################
def load_yaml():
    try:
        with open(YAML_FILE, 'r') as f:
            yaml_data = yaml.safe_load(f)

    except IOError:
        print("[finalizeRDB] Could not load finalizeRDB.yaml")
        os.exit(1)

    return yaml_data


##########################################
## files
##########################################
def add_files_to_redis(r, files):

    for file in files:

        print("[finalizeRDB] Adding key", file['key'], "with file:", file['file']) 
            
        with open(file['file'], "r") as f:
            file_contents = f.read()

        r.set(file['key'],file_contents)



##########################################
## Main event
##########################################

if __name__ == "__main__":

    r         = redis_connect()

    yaml_data = load_yaml()

    add_files_to_redis(r, yaml_data['files'])

    print("[finalizeRDB] Exiting.")
