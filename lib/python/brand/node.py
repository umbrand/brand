# BRAND node template
# Author: Mattia Rigotti
# Adapted from code by: David Brandman and Kushant Patel

import argparse
import gc
import json
import logging
import signal
import sys
import time
import numpy as np
import uuid
from redis import Redis

from .redis import RedisLoggingHandler, _ColourFormatter

class BRANDNode():
    def __init__(self):
        # parse input arguments
        argp = argparse.ArgumentParser()
        argp.add_argument('-n', '--nickname', type=str, required=True, default='node')
        argp.add_argument('-i', '--redis_host', type=str, required=True, default='localhost')
        argp.add_argument('-p', '--redis_port', type=int, required=True, default=6379)
        argp.add_argument('-s', '--redis_socket', type=str, required=False)
        argp.add_argument('--parameters', type=str, required=False, default='')
        args = argp.parse_args()

        len_args = len(vars(args))
        if(len_args < 3):
            print("Arguments passed: {}".format(len_args))
            print("Please check the arguments passed")
            sys.exit(1)

        self.NAME = args.nickname
        redis_host = args.redis_host
        redis_port = args.redis_port
        redis_socket = args.redis_socket
        
        # Setup basic console logging first
        self.setup_logging()

        # connect to Redis
        self.r = self.connectToRedis(redis_host, redis_port, redis_socket)

        # initialize parameters
        self.parameters = {}
        self.supergraph_id = '0-0'
        self.initializeParameters(args.parameters)

        # Now that we have Redis and parameters, add Redis logging
        self.add_redis_logging(loglevel=self.parameters.get("log", "INFO"))

        signal.signal(signal.SIGINT, self.terminate)
        sys.excepthook = self._handle_exception

        # Generate a unique ID for the node
        self.producer_gid_hex = uuid.uuid4().hex
        
        self._cursor = {}
    
    def setup_logging(self, loglevel: str = "INFO"):
        """
        Configure root logger with colourful console output.
        """
        # Build handlers
        console_handler = logging.StreamHandler(sys.stdout)
        console_fmt = _ColourFormatter(
            fmt=f"%(asctime)s [{self.NAME}] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S")
        console_handler.setFormatter(console_fmt)
        console_handler.setLevel(getattr(logging, loglevel.upper(), "INFO"))
        
        # Configure root logger
        logging.basicConfig(
            handlers=[console_handler],
            level=getattr(logging, loglevel.upper(), "INFO"),
            force=True,           # ← override any earlier basicConfig
        )
        
        # Store logger reference
        self.logger = logging.getLogger()
    
    def add_redis_logging(self, loglevel: str = "INFO"):
        """
        Add Redis logging to the logger

        Parameters
        ----------
        loglevel : str
            The log level to use for the Redis logging
        """
        redis_handler = RedisLoggingHandler(self.r, self.NAME)
        redis_handler.setLevel(getattr(logging, loglevel.upper(), "INFO"))
        self.logger.addHandler(redis_handler)

    def connectToRedis(self, redis_host, redis_port, redis_socket=None):
        """
        Establish connection to Redis and post initialized status to respective Redis stream
        If we supply a -h flag that starts with a number, then we require a -p for the port
        If we fail to connect, then exit status 1
        # If this function completes successfully then it executes the following Redis command:
        # XADD nickname_state * code 0 status "initialized"        
        """
        try:
            if redis_socket:
                r = Redis(unix_socket_path=redis_socket)
                self.logger.info(f"Redis connection established on socket:"
                      f" {redis_socket}")
            else:
                r = Redis(redis_host, redis_port, retry_on_timeout=True)
                self.logger.info(f"Redis connection established on host:"
                      f" {redis_host}, port: {redis_port}")
        except ConnectionError as e:
            self.logger.error(f"Error with Redis connection, check again: {e}")
            sys.exit(1)

        initial_data = {
            'code':0,
            'status':'initialized',
        }
        r.xadd(self.NAME + '_state', initial_data)

        return r

    def getParametersFromSupergraph(self, complete_supergraph=False):
        """
        Read node parameters from Redis

        Parameters
        ----------
        complete_supergraph : (optional) boolean
            False returns just the node's parameters.
            True returns the complete supergraph
            straight from the Redis xrange call.

        Returns
        -------
        new_params : list of dict
            Each list item will be a dictionary of the
            node's parameters in that supergraph
        """
        model_stream_entries = self.r.xrange(b'supergraph_stream', '('+self.supergraph_id, '+')

        if not model_stream_entries:
            return None
        
        self.supergraph_id = model_stream_entries[-1][0]
        self.supergraph_id = self.supergraph_id.decode('utf-8')

        if complete_supergraph:
            return model_stream_entries

        new_params = [{} for i in model_stream_entries] # {} means the node was not listed in the corresponding supergraph

        for i, entry in enumerate(model_stream_entries):

            model_data = json.loads(entry[1][b'data'].decode())

            for node in model_data['nodes']:
                if model_data['nodes'][node]['nickname'] == self.NAME:
                    new_params[i] = model_data['nodes'][node]['parameters']

        return new_params

    def initializeParameters(self, fallback_parameters: str = ''):
        """
        Read node parameters from Redis.
        If no parameters are found, use the fallback parameters.

        Parameters
        ----------
        fallback_parameters : str
            The fallback parameters to use if no parameters are found in Redis
        """
        if fallback_parameters != '':
            try:
                fallback_parameters = json.loads(fallback_parameters)
            except json.JSONDecodeError:
                self.logger.error(f"Invalid fallback parameters: {fallback_parameters}")
                sys.exit(1)
        else:
            fallback_parameters = None

        node_parameters = self.getParametersFromSupergraph()
        if node_parameters is None or len(node_parameters[-1].keys()) == 0:
            if fallback_parameters is None:
                self.logger.error(f"No model published to supergraph_stream in Redis")
                sys.exit(1)
            else:
                node_parameters = [fallback_parameters]
        
        # Make sure input and output streams are defined
        if 'input_streams' not in node_parameters[-1] or 'output_streams' not in node_parameters[-1]:
            self.logger.error(f"No input or output streams defined in node parameters")
            sys.exit(1)
        
        # Make sure input and output streams are dictionaries
        if not isinstance(node_parameters[-1]['input_streams'], dict) or not isinstance(node_parameters[-1]['output_streams'], dict):
            self.logger.error(f"Input and output streams must be dictionaries")
            sys.exit(1)

        for key,value in node_parameters[-1].items():
            self.parameters[key] = value

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
        self.logger.info('SIGINT received, Exiting')
        self.cleanup()
        self.r.close()
        gc.collect()
        sys.exit(0)

    def cleanup(self):
        # Does whatever cleanup is required for when a SIGINT is caught
        # When this function is done, it wriest the following:
        #     XADD nickname_state * code 0 status "done"
        pass

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """
        Handle uncaught exceptions by logging them.
        """
        if self.r.ping():
            self.logger.exception('', exc_info=(exc_type, exc_value, exc_traceback))
        else:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    def _next_seq(self):
        self._seq = getattr(self, "_seq", 0) + 1
        return self._seq
    
    def publish(self, stream: str, data: dict, parents: dict = None, pipeline=None):
        hdr = {
            "ts": int(time.monotonic_ns()),
            "seq": self._next_seq(),
            "producer_gid": self.producer_gid_hex,
            "node": self.NAME
        }
        if parents:
            hdr["parents"] = parents
        data_out = {"_hdr": json.dumps(hdr).encode()}
        
        data_out.update(data)
        
        if pipeline is not None:
            pipeline.xadd(stream, data_out)
        else:
            self.r.xadd(stream, data_out)
    
    def read_one(self, stream: str, block_ms: int = 0) -> dict:
        last = self._cursor.get(stream, "$")
        resp = self.r.xread({stream.encode(): last}, block=block_ms, count=1)
        if not resp:
            return None                  # timeout
        _, entries = resp[0]
        entry_id, fields = entries[0]
        entry_id = entry_id.decode()
        # Decode dictionary keys from bytes to strings
        decoded_fields = {}
        for key, value in fields.items():
            if isinstance(key, bytes):
                decoded_key = key.decode()
                decoded_fields[decoded_key] = value
            else:
                decoded_fields[key] = value
        self._cursor[stream] = entry_id  # advance cursor
        return entry_id, decoded_fields
    
    def read_latest(self, stream: str, count: int = 1):
        """
        Read the latest entries from a stream (equivalent to xrevrange).
        
        Parameters
        ----------
        stream : str or bytes
            The stream to read from
        count : int
            Number of latest entries to read (default: 1)
            
        Returns
        -------
        list
            List of (entry_id, fields) tuples, ordered from newest to oldest
        """
        if isinstance(stream, str):
            stream = stream.encode()
        
        resp = self.r.xrevrange(stream, '+', '-', count)
        
        result = []
        for entry_id, fields in resp:
            entry_id = entry_id.decode()
            # Decode dictionary keys from bytes to strings  
            decoded_fields = {}
            for key, value in fields.items():
                if isinstance(key, bytes):
                    decoded_key = key.decode()
                    decoded_fields[decoded_key] = value
                else:
                    decoded_fields[key] = value
            result.append((entry_id, decoded_fields))
        
        return result
    
    def read_n(self, stream: str, n: int = 1000, block_ms: int = None):
        """
        Read messages from a stream.
        
        Parameters
        ----------
        stream : str
            The stream to read from
        n : int
            Max number of entries to read at once (default: 1000)
        block_ms : int or None
            Milliseconds to block waiting for messages:
            - None (default): Non-blocking, returns immediately if no messages
            - 0: Block indefinitely until at least one message is available
            - >0: Wait up to block_ms milliseconds for messages
            
        Returns
        -------
        tuple or None
            A tuple containing (entry_ids, data_dict) where:
            - entry_ids: List of entry IDs corresponding to each message
            - data_dict: Dictionary with fields where each value is a list of values from all messages
            
            For example, if read_one returns (id, {'field': [1,2,3]}), read_n might return
            (['1234-0', '1235-0', '1236-0'], {'field': [[1,2,3], [4,5,6], [7,8,9]]})
            
            Returns None if no messages are available (or timeout occurred).
        """
        last = self._cursor.get(stream, "$")
        resp = self.r.xread({stream.encode(): last}, block=block_ms, count=n)
        if not resp:
            return None  # No messages available or timeout
            
        _, entries = resp[0]
        if not entries:
            return None  # No entries in stream
            
        # Initialize result dictionary with lists for each field
        result = {}
        entry_ids = []
        
        # Process each message
        for entry in entries:
            entry_id, fields = entry
            entry_id = entry_id.decode()
            entry_ids.append(entry_id)
            
            # Decode dictionary keys from bytes to strings
            for key, value in fields.items():
                if isinstance(key, bytes):
                    key = key.decode()
                if key == "_hdr":
                    value = json.loads(value.decode())
                
                # Add this value to the appropriate list in the result
                if key not in result:
                    result[key] = []
                result[key].append(value)
            
            # Update cursor to the latest entry
            self._cursor[stream] = entry_id
        
        return entry_ids, result
    
    def pipeline(self):
        """
        Create a Redis pipeline for batching multiple commands.
        
        Returns
        -------
        Redis pipeline
            A Redis pipeline object that can be passed to publish() and other methods
            
        Example
        -------
        # Using the pipeline with context manager (recommended)
        with self.pipeline() as pipe:
            self.publish("stream1", {"data": "value1"}, pipeline=pipe)
            self.publish("stream2", {"data": "value2"}, pipeline=pipe)
            # execute() is called automatically when exiting the context
            
        # Manual usage
        pipe = self.pipeline()
        self.publish("stream1", {"data": "value1"}, pipeline=pipe)
        self.publish("stream2", {"data": "value2"}, pipeline=pipe)
        pipe.execute()
        """
        return self.r.pipeline()