
##
import json
from flask import Flask, jsonify, escape, request, send_from_directory
from flask_cors import CORS, cross_origin
import yaml
import sys
import redis
import numpy as np

sys.path.insert(1, '../lib/redisTools/')
from redisTools import get_parameter_value

YAML_FILE = "rest.yaml"

# This is needed so that it doesn't do funky things with serving
app = Flask(__name__, static_url_path='') 
cors = CORS(app)

redis_ip = get_parameter_value(YAML_FILE,"redis_ip")
redis_port = get_parameter_value(YAML_FILE,"redis_port")
print("[rest] Initializing Redis with IP :" , redis_ip, ", port: ", redis_port)
r = redis.StrictRedis(host = redis_ip, port = redis_port, db = 0)


###############################################
## Deliver static site
###############################################

@app.route('/')
def deliverStatic():
    return app.send_static_file('index.html')

###############################################
## Return information about variables stored in Redis
###############################################

@app.route('/procs', methods=['GET'])
def get_proc_list():

    modules = get_parameter_value('rest.yaml', 'modules')

    return json.dumps({"modules" : modules})


@app.route('/procs/<proc>', methods=['GET'])
def get_single_proc(proc):

    fileName = proc + ".yaml"
    try:
        
        with open(fileName, 'r') as f:
            yamlData = yaml.safe_load(f)

    except IOError:
        return ""

    return json.dumps(yamlData['parameters'])


@app.route('/procs/<proc>/<name>', methods=['POST'])
def set_proc_value(proc, name):

    content = request.json
    print(content['name'],content['value'])
    
    if content['value'] == 'False':
        content['value'] = 0

    if content['value'] == 'True':
        content['value'] = 1

    r.set(content['name'],content['value'])


    return json.dumps({"name" : "floatTest", "status" : "OK"})

###########################################################
## streams
###########################################################
@app.route('/streams', methods=['GET'])
def getStreams():

    streams = []
    
    if r.exists("streamUDP"):
        streamUDP_result = r.xinfo_stream("streamUDP")
        streamUDP_keys   = [x.decode('utf-8') for x in streamUDP_result['last-entry'][1].keys()]
        streamUDP        = {
                "name"       : "streamUDP",
                "keys"       : streamUDP_keys,
                "parameters" : ["downsample"]
                }
        streams = streams + [streamUDP]
            
    if r.exists("pipe"):
        pipe_result = r.xinfo_stream("pipe")
        pipe_keys   = [x.decode('utf-8') for x in pipe_result['last-entry'][1].keys()]
        pipe = {
                "name" : "pipe",
                "keys" : pipe_keys,
                "parameters" : ["downsample"]
                }
        streams = streams + [pipe]
            


    output = { "streams" : streams }

    return json.dumps(output)
            


###########################################################
## /streams/pipe
###########################################################

@app.route('/streams/pipe/<key>', methods=['GET'])
def pipe(key):

    downsample = request.args.get('downsample', 10, type=int)

    key = key.encode('utf-8')

    # This will return an array of entries
    # Each entry has [0] --> timestamp
    # [1] --> A dictionary
    data = r.xrevrange("pipe", count=1000)

    if key not in data[0][1].keys():
        output = {"error" : str(key) + " is not a key in pipe"}
        return json.dumps(output)

    # If we're here then we know we have a valid key
    # From the dictionary, return the dictionary entry of the key
    # and convert it into a float. Create a comprehension over all of the
    # returned data

    y      = [float(x[1][key]) for x in data]
    y      = y[::downsample]
    x      = list(reversed(range(len(y))))
    name   = str(key)
    xTitle = "Time"
    yTitle = "Power"
    maxID  = data[0][0].decode('utf-8')

    output = { "x"      : x
             , "y"      : y
             , "name"   : name
             , "xTitle" : xTitle
             , "yTitle" : yTitle
             , "maxID"  : maxID
             }

    print(output)

    return json.dumps(output)

###########################################################
## /streams/streamUDP
###########################################################

@app.route('/streams/streamUDP/<key>', methods=['GET'])
def udpStream(key):

    key = key.encode('utf-8')

    downsample = request.args.get('downsample', 200, type=int)


    # This will return an array of entries
    # Each entry has [0] --> timestamp
    # [1] --> A dictionary
    data = r.xrevrange("streamUDP", count=1000)

    if key not in data[0][1].keys():
        output = {"error" : key + " is not a key in streamUDP"}
        return json.dumps(output)

    # If we're here then we know we have a valid key
    # From the dictionary, return the dictionary entry of the key
    # and convert it into a float. Create a comprehension over all of the
    # returned data

    y      = [float(x[1][key]) for x in data]
    y      = y[::downsample]
    x      = list(reversed(range(len(y))))
    name   = "Raw_chan0"
    xTitle = "Time"
    yTitle = "Voltage"
    maxID  = data[0][0].decode('utf-8')

    output = { "x"      : x
             , "y"      : y
             , "name"   : name
             , "xTitle" : xTitle
             , "yTitle" : yTitle
             , "maxID"  : maxID
             }

    return json.dumps(output)

###############################################
## Return information about variables stored in Redis
###############################################

@app.route('/runtimes', methods=['GET'])
def get_runtimes():

    modules = get_parameter_value('rest.yaml', 'runtimes')

    return json.dumps({"runtimes" : modules})


@app.route('/runtimes/<proc>', methods=['GET'])
def get_single_runtime(proc):

    proc = proc.encode('utf-8')


    # This will return an array of entries
    # Each entry has [0] --> timestamp
    data = r.xrevrange(proc, count=1000)

    # For each of the timepoints, turn them into utf-8 strings
    # and then take the part that is before the dash
    # And then reverse the list and compute the diffs

    y      = [int(x[0].decode('utf-8').split("-")[0]) for x in data]
    diffs  = np.diff(y[::-1])


    output = { "name"   : proc.decode('utf-8')
             , "length" : len(diffs)
             , "mean"   : diffs.mean()
             , "std"    : diffs.std()
             }


    return json.dumps({"data" : output})



###############################################
## Run the script
###############################################

app.run(host='0.0.0.0',debug=True)



