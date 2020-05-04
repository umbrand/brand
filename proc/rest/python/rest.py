
##
import json
from flask import Flask, jsonify, escape, request, send_from_directory
from flask_cors import CORS, cross_origin
import yaml
import sys
import redis

VERBOSE = True

app = Flask(__name__)
cors = CORS(app)

r = redis.StrictRedis(host='localhost', port=6379, db=0)


@app.route('/<proc>/<name>', methods=['POST'])
def test(proc, name):

    content = request.json
    print(content['name'],content['value'])
    
    if content['value'] == 'False':
        content['value'] = 0

    if content['value'] == 'True':
        content['value'] = 1

    r.set(content['name'],content['value'])


    return json.dumps({"name" : "floatTest", "status" : "OK"})

@app.route('/<proc>')
def dumpJson(proc):

    fileName = proc + '.yaml'

    with open(fileName) as file:
        documents = yaml.safe_load(file)

    return json.dumps(documents)




app.run(debug=True)



# @app.route('/user')
# def user():
#     output = { "data" : {"name":'Alice',"email":'alice@email.com',"age":10, "id":1}}
      
#     return output

# @app.route('/error')
# def myError():
#     return {"errors" : [ { "email" : "taken"} , {"age": "> 16"}]}
