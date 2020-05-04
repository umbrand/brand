# Some helpers to work with Redis

import sys
import yaml
import redis
import datetime

yamlFolderPath = '/home/david/Documents/Projects/EmorySpeech/code/yaml/'

#############################################
#############################################
## Load the YAML file
#############################################
#############################################
def initializeRedisFromYAML(proc):

    fileName = yamlFolderPath + proc + '.yaml'

    print("[InitializeFromRedis] Loading configuration file: " , fileName)

    try:
        with open(fileName, 'r') as f:
            yamlData = yaml.safe_load(f)

    except IOError:
        Sys.exit( "Could not read file:", fileName)

    redisIP = ""
    redisPort = ""
    for record in yamlData:
        if record['name'] == "redisIP":
            redisIP = record['value']
        if record['name'] == "redisPort":
            redisPort = record['value']

    print("[InitializeFromRedis] Initializing Redis with IP : " , redisIP, ", port: ", redisPort)

    r = redis.Redis(host=redisIP, port=redisPort, db=0)

    print("[InitializeFromRedis] Here are the other variables:")

    for record in yamlData:
        if type(record['value']) == bool:
            if record['value']:
                record['value'] = 1
            else:
                record['value'] = 0
       
        print("     Record: ", record['name'], ": ", record['value'])
        r.set(record['name'], record['value'])
    
    return r

#############################################
## Publishing data from Redis
#############################################

def publish(r, name, val):

    # Format what now is in the sqlite3 format, removing the sub-millisecond precision
    timeStamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[0:-3]
    str = timeStamp + "," + val
    r.publish(name, str)



#############################################
## Getting data from Redis
#############################################

def getFloat(r, name):
    return float(r.get(name))

def getInt(r, name):
    return int(r.get(name))

def getString(r, name):
    return (r.get(name)).decode('utf-8')

def getFloatLRange(r, name, start, end):
    return [float(x) for x in r.lrange(name, start, end)]

def getIntLRange(r, name, start, end):
    return [int(x) for x in r.lrange(name, start, end)]

def getStringLRange(r, name, start, end):
    return [x.decode('utf-8') for x in r.lrange(name, start, end)]
