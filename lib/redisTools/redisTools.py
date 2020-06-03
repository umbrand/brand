# Some helpers to work with Redis

import sys
import yaml
import redis
import datetime
import sys
import argparse


#############################################
#############################################
## Load the YAML file
#############################################
#############################################

# This function is designed to be used from a .c code, which is
# going to be reading the output of the stream. So it shouts
# no errors. Probably shouldn't use this code in pythonesque code

def get_parameter_value(fileName, field):
    try:
        with open(fileName, 'r') as f:
            yamlData = yaml.safe_load(f)

    except IOError:
        return ""

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


#############################################
#############################################

def initializeRedisFromYAML(fileName):

    # fileName = yamlFolderPath + proc + '.yaml'

    print("[InitializeFromRedis] Loading configuration file: " , fileName)

    try:
        with open(fileName, 'r') as f:
            yamlData = yaml.safe_load(f)

    except IOError:
        sys.exit( "Could not read file:", fileName)

    # Start by specifically reading the IP and port based on YAML configuration

    redisIP = ""
    redisPort = ""
    for record in yamlData['parameters']:
        if record['name'] == "redis_ip":
            redisIP = record['value']
        if record['name'] == "redis_port":
            redisPort = record['value']

    if redisIP == "" or redisPort == "":
        print("[InitializeFromRedis] Your configuration file does not include the variables redis_ip and redis_port. Aborting!")
        sys.exit(1)


    print("[InitializeFromRedis] Initializing Redis with IP : " , redisIP, ", port: ", redisPort)

    # Having gotten to this point we can now initialize all of the variables

    r = redis.Redis(host=redisIP, port=redisPort, db=0)

    print("[InitializeFromRedis] Here are the other variables:")

    # Get the name of the process based on the filename. Expect: /path/to/processName.yaml
    processName = fileName.split("/")[-1].split(".")[0]

    for record in yamlData['parameters']:

        record['name'] = processName + "_" + record['name']

        r.delete(record['name'])

        print("     Record: ", record['name'], ": ", record['value'])


        if type(record['value']) == bool:
            if record['value']:
                record['value'] = 1
            else:
                record['value'] = 0

        if type(record['value']) == list:
            for val in record['value']:
                r.rpush(record['name'],val)

        else:
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

#############################################
## Running code like a script
#############################################

def main():

    description = """
        Tools for initializing processes. The default behavior is to look into a YAML file
        and then initialize all of the variables from the YAML script into Redis. This
        behavior, by default, is verbose. If you supply an --ip or --port flag, then
        the script will look specifically for the redis_ip or redis_port variable from
        the script and print it. This should be used only for .c processes"""

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--name', help='Return the value in the YAML file')
    parser.add_argument('file', default="", type=str, help='The YAML file to be loaded')

    args = parser.parse_args()

    if args.name:
        print(get_parameter_value(args.file, args.name), end="")
    else:
        initializeRedisFromYAML(args.file)



if __name__ == '__main__':
    main()




