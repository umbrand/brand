
##
import json
from flask import Flask, jsonify, escape, request, send_from_directory
from flask_cors import CORS, cross_origin
import yaml
import sys
import redis

VERBOSE = True

# This is needed so that it doesn't do funky things with serving
app = Flask(__name__,
        static_url_path='') 
cors = CORS(app)

r = redis.StrictRedis(host='localhost', port=6379, db=0)

###############################################
## Deliver static site
###############################################

@app.route('/')
def deliverStatic():
    return app.send_static_file('index.html')

###############################################
## Return information about variables stored in Redis
###############################################

@app.route('/procs/<proc>/<name>', methods=['POST'])
def test(proc, name):

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

    
    streamUDP_result = r.xinfo_stream("streamUDP")
    streamUDP_keys   = [x.decode('utf-8') for x in streamUDP_result['last-entry'][1].keys()]
    streamUDP        = {
            "name"       : "streamUDP",
            "keys"       : streamUDP_keys,
            "parameters" : ["downsample"]
            }
            
    pipe_result = r.xinfo_stream("pipe")
    pipe_keys   = [x.decode('utf-8') for x in pipe_result['last-entry'][1].keys()]
    pipe = {
            "name" : "pipe",
            "keys" : pipe_keys,
            "parameters" : ["downsample"]
            }
            


    output = { "streams" : [streamUDP, pipe] }

    return json.dumps(output)
            


###########################################################
## /streams/streamUDP
###########################################################

@app.route('/streams/pipe/<key>', methods=['GET'])
def pipe(key):

    downsample = request.args.get('downsample', 1, type=int)

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


@app.route('/streams/streamUDP/<key>', methods=['GET'])
def udpStream(key):

    key = key.encode('utf-8')

    downsample = request.args.get('downsample', 1, type=int)


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



app.run(host='192.168.0.2',debug=True)



# @app.route('/user')
# def user():
#     output = { "data" : {"name":'Alice',"email":'alice@email.com',"age":10, "id":1}}
      
#     return output

# @app.route('/error')
# def myError():
#     return {"errors" : [ { "email" : "taken"} , {"age": "> 16"}]}
    # OK, get the dictionary and find the key called 'raw'. Turn it into
    # a string and then split it at the first comma, use only the first
    # entry of this split and then turn all of the numbers into a float
    # y =[float(x[1][b'raw'].decode('utf-8').split(',',1)[0]) for x in data]
