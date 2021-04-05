#!/usr/bin/env python

##
import json
from flask import Flask, jsonify, escape, request, send_from_directory, render_template
from flask_cors import CORS, cross_origin
import yaml
import sys
import redis
import numpy as np
import struct
from flask_socketio import SocketIO, join_room, emit, send
import threading
import time
import eventlet
eventlet.monkey_patch()

sys.path.insert(1, '../lib/redisTools/')
from redisTools import get_parameter_value

###############################################
## Initializations
###############################################

YAML_FILE = "rest.yaml"

app = Flask(__name__, static_url_path='') 
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
# socketio = SocketIO(app, logger=True, engineio_logger=True, cors_allowed_origins="*")
socketio = SocketIO(app, cors_allowed_origins="*")


# Initialize our connection to Redis

redis_ip = get_parameter_value(YAML_FILE,"redis_ip")
redis_port = get_parameter_value(YAML_FILE,"redis_port")
stream_name = get_parameter_value(YAML_FILE,"stream_name")
num_channels = get_parameter_value(YAML_FILE,"num_channels") # number of channels per sample array
num_samples = get_parameter_value(YAML_FILE, "num_samples") # number of samples per stream
disp_channel = get_parameter_value(YAML_FILE, "disp_channel") # channel to display -- for pulling things out of the array
print("[rest] Initializing Redis with IP :" , redis_ip, ", port: ", redis_port)
r = redis.StrictRedis(host = redis_ip, port = redis_port, db = 0)


###############################################
## Deliver static site
###############################################

@app.route('/')
def index():
    rest_ip   = get_parameter_value('rest.yaml', 'rest_ip')
    rest_port = get_parameter_value('rest.yaml', 'rest_port')

    yaml_url = "http://" + rest_ip + ":" + str(rest_port)

    return render_template('index.html', yaml_url = yaml_url)

###############################################
## Emit socket stream info
###############################################

@socketio.on('connect')
def handle_connect():
    # r.hset("userHash", request.sid, "0")
    # emit('serverAssignID', request.sid)
    print("---------------------------")
    print("New Connection: " , request.sid)
    print("---------------------------")


# This code sits in a loop and emits streaming data
# Probably not the most effective way to do it, but certainly very easy to implement
# Will need to do a more precise job in the future, especially since I'm pretty sure
# this method will only work for one person being connected at at time

# Read from the /tmp/stream file, and then use that for emitting data

def emitStreamData():

    print("[rest] streaming data") 
    while True:
        try:
            
            with open('/tmp/stream', 'r') as f:
                jsonData = json.load(f)

            key = jsonData['key']

            if not r.exists(jsonData['stream']):
                time.sleep(0.5)
                continue

            # Get the first entry
            firstTimestamp = r.xinfo_stream(jsonData['stream'])['first-entry'][0].decode('utf-8').split('-')[0]
            firstTimestamp = int(firstTimestamp)

            # Get the current entry
            xrevrange_output = r.xrevrange(jsonData['stream'], min = '-', max = '+', count=1)[0]
            thisTimestamp = xrevrange_output[0].decode('utf-8').split('-')[0]
            thisTimestamp = int(thisTimestamp)

            # Compute the difference
            seconds = str((thisTimestamp - firstTimestamp) / 1000)

            # Code specifically for cerebusAdapter
            # Unpack the most recent entry and construct a json struct
            if jsonData['stream'] == stream_name:
                if 'samples' in key:
                    val = struct.unpack('h' * num_channels * num_samples,
                            xrevrange_output[1][key.encode('utf-8')])[num_samples*(disp_channel-1):num_samples*disp_channel]
                    
                    output = {'time' : float(seconds)
                            , 'value' : float(val[0])
                            , 'xTitle' : "Time (seconds)"
                            , 'yTitle' : "Voltage (mv)" 
                            , 'title'  : ("Streaming: " + str(disp_channel))}
                    socketio.emit('stream_newdata', json.dumps(output), include_self=True)



                if 'udp_received_time' in key:
                    val = np.array(struct.unpack('I' * num_samples, xrevrange_output[1][key.encode('utf-8')]))
                    val = np.append(0,val[1:] - val[:-1])
                    output = {'time' : float(seconds)
                            , 'value' : float(val[0])
                            , 'xTitle' : "Time (s)"
                            , 'yTitle' : "UDP packet time delta" 
                            , 'title'  : ("UDP Packet Latencies")}
                    socketio.emit('stream_newdata', json.dumps(output), include_self=True)

        except IOError:
            pass

        time.sleep(0.1)



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
##
##
## Code for managing streams
##
##
###########################################################

@app.route('/streams', methods=['GET'])
def getStreams():

    streams = []
    
            
    if r.exists("pipe"):
        stream_result = r.xinfo_stream("pipe")
        stream_keys   = [x.decode('utf-8') for x in stream_result['last-entry'][1].keys()]
        stream        = {
                "name"       : "pipe",
                "keys"       : stream_keys,
                "parameters" : ["downsample"]
                }
        streams = streams + [stream]
            
    if r.exists(stream_name):
        stream_result = r.xinfo_stream(stream_name)
        stream_keys   = [x.decode('utf-8') for x in stream_result['last-entry'][1].keys()]
        #stream_keys   = [x for x in stream_keys if "chan" in x]
        # LOGIC HERE FOR INCLUDING ONLY THOSE THAT START WITH CHAN
        stream        = {
                "name" : stream_name,
                "keys" : stream_keys,
                "parameters" : []
                }
        streams = streams + [stream]


    output = { "streams" : streams }

    return json.dumps(output)
            
###########################################################
## /streams/cerebusAdapter_neural
###########################################################



@app.route('/streams/<stream>/<key>', methods=['POST'])
def writeStream(stream, key):

    val = { 'stream' : stream,
            'key'    : key,
          }  

    try:
        with open('/tmp/stream', 'w') as f:
            f.write(json.dumps(val))

    except IOError:
        print("[rest] Could not write to /tmp/stream")


    return json.dumps(val)


@app.route('/streams/cerebusAdapter_neural/<disp_channel>', methods=['GET'])
def cerebusAdapter_neural(disp_channel):


    downsample = request.args.get('downsample', 100, type=int)

    # This will return an array of entries
    # Each entry has [0] --> timestamp
    # [1] --> A dictionary
    data = r.xrevrange("cerebusAdapter_neural", count=1000)

    # If we're here then we know we have a valid key
    # From the dictionary, return the dictionary entry of the key
    # and convert it into a float. Create a comprehension over all of the
    # returned data

    y = []
    for single_data in data:
        val = struct.unpack('H' * num_channels * num_samples, single_data[1])
        val = val[(disp_channel*num_samples,(disp_channel+1)*num_samples)]
        y = np.append(y, np.array(val, dtype='int'))

    y      = y[::downsample]
    x      = list(reversed(range(len(y))))
    name   = str(disp_channel)
    xTitle = "Cerebus sample"
    yTitle = "Raw voltage"
    maxID  = data[0][0].decode('utf-8')

    print(len(y))

    output = { "x"      : x
             , "y"      : y.tolist()
             , "name"   : name
             , "xTitle" : xTitle
             , "yTitle" : yTitle
             , "maxID"  : maxID
             }

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


# thread = threading.Thread(target=emitStreamData)
# thread.start()

eventlet.spawn(emitStreamData)

# app.run(host='0.0.0.0',debug=True)
socketio.run(app, host='0.0.0.0')



################################################
# Good code for later

# @app.route('/')
# def deliverStatic():
#     return app.send_static_file('index.html')


