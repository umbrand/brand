# BRAND node template
# Author: Mattia Rigotti
# Adapted from code by: David Brandman and Kushant Patel

import sys
import argparse
from redis import Redis
import logging
import signal
import json
import time

class BRANDNode():
    def __init__(self):
        
        # parse input arguments
        argp = argparse.ArgumentParser()
        argp.add_argument('-n', '--nickname', type=str, required=True, default='node')
        argp.add_argument('-hs', '--redis_host', type=str, required=True, default='localhost')
        argp.add_argument('-p', '--redis_port', type=int, required=True, default=6379)
        args = argp.parse_args()
        
        len_args = len(vars(args))
        if(len_args < 3):
            print("Arguments passed: {}".format(len_args))
            print("Please check the arguments passed")
            sys.exit(1)        

        self.NAME = args.nickname
        redis_host = args.redis_host
        redis_port = args.redis_port 
        
        # connect to Redis
        self.r = self.connectToRedis(redis_host, redis_port)

        # initialize parameters
        self.parameters = {}
        self.initializeParameters()

        # set up logging
        loglevel = self.parameters['log']
        numeric_level = getattr(logging, loglevel.upper(), None)

        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)

        logging.basicConfig(format=f'[{self.NAME}] %(levelname)s: %(message)s',
                            level=numeric_level) 
        
        signal.signal(signal.SIGINT, self.terminate)

        # # initialize output stream entry data
        # self.sync_dict = {}
        # self.sync_dict_json = json.dumps(self.sync_dict)
        
        # self.output_entry = {
        #     self.time_key: time.monotonic(), 
        #     self.sync_key: self.sync_dict_json.encode(), 
        # }

        # self.output_stream = "default"

        #logging.info('Redis connection established and parameters loaded')    

    def connectToRedis(self, redis_host, redis_port):
        """
        Establish connection to Redis and post initialized status to respective Redis stream
        If we supply a -h flag that starts with a number, then we require a -p for the port
        If we fail to connect, then exit status 1
        # If this function completes successfully then it executes the following Redis command:
        # XADD nickname_state * code 0 status "initialized"        
        """
        
        #redis_connection_parse = argparse.ArgumentParser()
        #redis_connection_parse.add_argument('-hs', '--redis_host', type=str, required=True, default='localhost')
        #redis_connection_parse.add_argument('-p', '--redis_port', type=int, required=True, default=6379)
        #redis_connection_parse.add_argument('-n', '--nickname', type=str, required=True, default='redis_v0.1')

        #args = redis_connection_parse.parse_args()
        #len_args = len(vars(args))
        #print("Redis arguments passed:{}".format(len_args))
        
        try:
            r = Redis(redis_host, redis_port, retry_on_timeout=True)
            print(f"[{self.NAME}] Redis connection established on host: {redis_host}, port: {redis_port}")
        except ConnectionError as e:
            print(f"[{self.NAME}] Error with Redis connection, check again: {e}")
            sys.exit(1)     
        
        initial_data = {
            'code':0,
            'status':'initialized',
        }   
        r.xadd(self.NAME + '_state', initial_data)
        
        return r
    
    def initializeParameters(self):
        """
        Read node parameters from Redis.
        ...
        """
        model_stream_entry = self.r.xrevrange(b'supergraph_stream', '+', '-', 1)[0]
        
        if model_stream_entry is None:
            print(f"[{self.NAME}] No model published to supergraph_stream in Redis")
            sys.exit(1)

        entry_id, entry_dict = model_stream_entry

        model_data = json.loads(entry_dict[b'data'].decode())

        # self.sync_key = model_data['sync_key'].encode()
        # self.time_key = model_data['time_key'].encode()

        node_parameters = {}
        for node in model_data['nodes']:
            if model_data['nodes'][node]['nickname'] == self.NAME:
                node_parameters = model_data['nodes'][node]['parameters']
                print(type(model_data['nodes'][node]['parameters']))
                break
        
        #for parameter in node_parameters:
            #self.parameters[parameter['name']] = parameter['value']
        for key,value in node_parameters.items():
            self.parameters[key] = value
                
        #print(self.parameters)

    # def initializeMain(self):
    #     """
    #     Logic for initializing anything else that needs to be initialized once the
    #     parameters are set for the function
    #     """
    #     pass

    def run(self):
        
        while True:
            self.work()
            self.updateParameters()

    def work(self):
        """
        # This is the business logic for the function. 
        # At the end of its cycle, it should output the following:
        # XADD nickname_streamOutputName [inputRun M] run nRuns parameter N name1 value1 name2 value2
        # where streamOutputName is the name provided in the YAML file (usually: output)
        # and the name1 is the name variable for the output stream, and the value being the payload
        # and N is the value of parameter_count global variable
        # Note there is an exact match between the name value pairs and what is specified in the YAML
        # If inputs is not [] in the YAML file, then inputRun contains the 
        # nRuns count of the previous input used for populating this stream output       
        """
        pass

    # def write_brand(self):
    
    #     self.sync_dict_json = json.dumps(self.sync_dict)
        
    #     self.output_entry[self.time_key] = time.monotonic()
    #     self.output_entry[self.sync_key] = self.sync_dict_json.encode()

    #     self.r.xadd(self.output_stream, self.output_entry)


    def updateParameters(self):
        """
        This function reads from the nickname_parameters stream, 
        and knows how to parse all parameters that (1) do not have static variable
        specified, or (2) are static: false specified
        It does not block on the XREAD call. Whenever there is a new stream value,
        it assumes that the new value is meaningful (since it should have been checked
        by the supervisor node) and then updates the parameters = {} value
        If this function updates the parameters{} dictionary, then it increments parameter_count
        """
        pass

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        self.r.close()
        #self.sock.close()
        sys.exit(0)

    def cleanup(self):
        # Does whatever cleanup is required for when a SIGINT is caught
        # When this function is done, it wriest the following:
        #     XADD nickname_state * code 0 status "done"
        pass



class BRANDNodeOld():
    def __init__(self):
        
        # parse input arguments
        self.NAME = sys.argv[2]  # name of this node
        self.YAML_FILE = sys.argv[1]
        
        # connect to Redis
        self.r = initializeRedisFromYAML(self.YAML_FILE, self.NAME)

        # initialize parameters
        self.parameters = {}
        self.initializeParameters()

        # set up logging
        #loglevel = self.parameters['log']
        numeric_level = getattr(logging, loglevel.upper(), None)

        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)

        logging.basicConfig(format=f'[{self.NAME}] %(levelname)s: %(message)s',
                            level=numeric_level) 
        
        signal.signal(signal.SIGINT, self.terminate)

        #logging.info('Redis connection established and parameters loaded')    

    def connectToRedis(self, redis_host, redis_port):
        """
        Establish connection to Redis and post initialized status to respective Redis stream
        If we supply a -h flag that starts with a number, then we require a -p for the port
        If we fail to connect, then exit status 1
        # If this function completes successfully then it executes the following Redis command:
        # XADD nickname_state * code 0 status "initialized"        
        """
        
        #redis_connection_parse = argparse.ArgumentParser()
        #redis_connection_parse.add_argument('-hs', '--redis_host', type=str, required=True, default='localhost')
        #redis_connection_parse.add_argument('-p', '--redis_port', type=int, required=True, default=6379)
        #redis_connection_parse.add_argument('-n', '--nickname', type=str, required=True, default='redis_v0.1')

        #args = redis_connection_parse.parse_args()
        #len_args = len(vars(args))
        #print("Redis arguments passed:{}".format(len_args))
        
        try:
            r = Redis(redis_host, redis_port, retry_on_timeout=True)
            print(f"[{self.NAME}] Redis connection established on host: {redis_host}, port: {redis_port}")
        except ConnectionError as e:
            print(f"[{self.NAME}] Error with Redis connection, check again: {e}")
            sys.exit(1)     
        
        initial_data = {
            'code':0,
            'status':'initialized',
        }   
        r.xadd(self.NAME + '_state', initial_data)
        
        return r
    
    def initializeParameters(self):
        """
        Read node parameters from Redis.
        ...
        """
        model_stream_entry = self.r.xrevrange(b'supergraph_stream', '+', '-', 1)[0]
        
        if model_stream_entry is None:
            print(f"[{self.NAME}] No model published to supergraph_stream in Redis")
            sys.exit(1)

        entry_id, entry_dict = model_stream_entry

        model_data = json.loads(entry_dict[b'data'].decode())

        #print(model_data)

        node_parameters = {}
        for node in model_data['nodes']:
            if model_data['nodes'][node]['nickname'] == self.NAME:
                node_parameters = model_data['nodes'][node]['parameters']
                break
        
        for parameter in node_parameters:
            self.parameters[parameter['name']] = parameter['value']

        #print(self.parameters)

    # def initializeMain(self):
    #     """
    #     Logic for initializing anything else that needs to be initialized once the
    #     parameters are set for the function
    #     """
    #     pass

    def run(self):
        
        while True:
            self.work()
            self.updateParameters()

    def work(self):
        """
        # This is the business logic for the function. 
        # At the end of its cycle, it should output the following:
        # XADD nickname_streamOutputName [inputRun M] run nRuns parameter N name1 value1 name2 value2
        # where streamOutputName is the name provided in the YAML file (usually: output)
        # and the name1 is the name variable for the output stream, and the value being the payload
        # and N is the value of parameter_count global variable
        # Note there is an exact match between the name value pairs and what is specified in the YAML
        # If inputs is not [] in the YAML file, then inputRun contains the 
        # nRuns count of the previous input used for populating this stream output       
        """
        pass

    def updateParameters(self):
        """
        This function reads from the nickname_parameters stream, 
        and knows how to parse all parameters that (1) do not have static variable
        specified, or (2) are static: false specified
        It does not block on the XREAD call. Whenever there is a new stream value,
        it assumes that the new value is meaningful (since it should have been checked
        by the supervisor node) and then updates the parameters = {} value
        If this function updates the parameters{} dictionary, then it increments parameter_count
        """
        pass

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        self.r.close()
        #self.sock.close()
        sys.exit(0)

    def cleanup(self):
        # Does whatever cleanup is required for when a SIGINT is caught
        # When this function is done, it wriest the following:
        #     XADD nickname_state * code 0 status "done"
        pass