import argparse
import json
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime

import coloredlogs
import yaml
from redis import Redis

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG', logger=logger)



class Supervisor:
    def __init__(self):
        ''' Initialize the supervisor class and load the graph file loaded from the command line '''
        self.model = {}
        self.r = None
        self.parent = None
        self.children = []

        self.BRAND_BASE_DIR = os.getcwd()

        self.participant_id = "Participant0"
        self.session_number = 0

        self.save_path = os.path.join(self.BRAND_BASE_DIR,
                                "../Data",
                                self.participant_id,
                                "Session"+str(self.session_number),
                                "RawData")
        self.save_path_rdb = os.path.join(self.save_path,
                                "RDB")
        self.save_path_nwb = os.path.join(self.save_path,
                                "NWB")

        self.state = ("initialized", "parsing", "graph failed", "running",
                      "published", "stopped/not initialized")

        self.graph_file = None

        signal.signal(signal.SIGINT, self.terminate)

        graph_dict = self.parse_args()

        self.start_redis_server()
        self.r.xadd("graph_status", {'status': self.state[5]})

        if self.graph_file is not None: self.load_graph(graph_dict)

    def handler(signal_received,self):
        raise KeyboardInterrupt("SIGTERM received")

    def child_process_handler(self,node_stream_name):
        '''
        Child handler
        '''
        logger.debug("Checking the status from the node")
        self.r.xread({str(node_stream_name+"_state"):"$"},count=1,block=5000)

    def parse_args(self)->dict:
        ''' Parse the graph file loaded from the command line and return the graph dictionary using -g option/cmdline argument
        Returns:
            graph_dict: graph dictionary
        '''
        ap =  argparse.ArgumentParser()
        ap.add_argument("-g", "--graph", required=False, help="path to graph file")
        ap.add_argument("-i", "--host", required=False, help="ip address to bind redis server to")
        ap.add_argument("-p", "--port", required=False, help="port to bind redis server to")
        ap.add_argument("-c", "--cfg", required=False, help="cfg file for redis server")
        args = ap.parse_args()

        self.redis_args = []

        if args.cfg is not None:
            self.redis_args.append(args.cfg)
        else:
            self.redis_args.append(
                os.path.join(self.BRAND_BASE_DIR,
                             'supervisor/redis.supervisor.conf'))
        if args.host is not None:
            self.redis_args.append('--bind')
            self.redis_args.append(args.host)
            self.host = args.host
        else:
            self.host = '127.0.0.1'
        if args.port is not None:
            self.redis_args.append('--port')
            self.redis_args.append(args.port)
            self.port = args.port
        else:
            self.port = 6379

        self.graph_file = args.graph
        graph_dict = {}
        if self.graph_file is not None:
            try:
                with open(args.graph, 'r') as stream:
                    graph_dict = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.error("Error in parsing the graph file"+str(exc))
                sys.exit(1)
            logger.info("Graph file parsed successfully")
        return graph_dict


    def search_node_yaml_file(self,module,name)->str:
        ''' Search the node yaml file and return the yaml file path 
        Args:
            module: module name
            name : node name
        '''
        # change the working directory to the module directory
        directory = [os.path.join(self.BRAND_BASE_DIR, module, 'nodes', name)]
        for dir in directory:
            for file in os.listdir(dir):
                if file.endswith(".yaml"):
                    yaml_file = os.path.join(dir, file)
                    logger.info("yaml file path: %s" % yaml_file)
        return yaml_file


    def search_node_bin_file(self,module,name)->str:
        ''' Search the node bin/exec file and return the bin/exec file path 
        Args:
            module: module name
            name : node name
        '''
        directory = [os.path.join(self.BRAND_BASE_DIR, module, "nodes", name)]
        for dir in directory:
            for file in os.listdir(dir):
                if file.endswith(".bin") or file.endswith(".out"):
                    bin_file = os.path.join(dir, file)
                    logger.info("bin/exec file path: %s" % bin_file)
        return bin_file


    def get_graph_status(self,state)->str:
        '''
        Utility function to get the graph status
        Args:
            state: graph status from redis stream using xrevrange
        '''
        if state:
            key,messages = state[0]
            current_status = messages[b'status'].decode("utf-8")
        else:
            logger.info("No status found in redis stream")
        return current_status


    def start_redis_server(self):
        redis_command = ['redis-server'] + self.redis_args
        logger.info('Starting redis: ' + ' '.join(redis_command))
        # get a process name by psutil
        proc = subprocess.Popen(redis_command, stdout=subprocess.PIPE)
        try:
            out, _ = proc.communicate(timeout=1)
            logger.debug(out.decode())
            if 'Address already in use' in str(out):
                logger.warning("Could not run redis-server (address already in use).")
                logger.warning(
                    "Assuming that the process using the TCP port"
                    " is another redis-server instance. Continuing.")
            else:
                raise Exception("Could not run redis-server. Aborting.")
        except subprocess.TimeoutExpired:  # no error message received
            logger.info('redis-server is running')
        self.r = Redis(self.host,self.port,socket_connect_timeout=1)

        # Set rdb save directory
        if not os.path.exists(self.save_path_rdb):
            os.makedirs(self.save_path_rdb)
        self.r.config_set('dir', self.save_path_rdb)
        logger.info(f"RDB save directory set to {self.save_path_rdb}")
        # Set new rdb filename 
        self.rdb_filename =  'idle_' + datetime.now().strftime(r'%y%m%dT%H%M') + '.rdb'
        self.r.config_set('dbfilename', self.rdb_filename)
        logger.info(f"RDB file name set to {self.rdb_filename}")
        


    def load_graph(self,graph_dict,rdb_filename=None):
        ''' Running logic for the supervisor graph, establishes a redis connection on specified host & port  
        Args:
            graph_dict: graph dictionary
        '''
        nodes = graph_dict['nodes']

        self.graph_name = graph_dict['metadata']['graph_name']

        # Set rdb filename
        if rdb_filename is None:
            self.rdb_filename =  self.graph_name + '_' + datetime.now().strftime(r'%y%m%dT%H%M') + '.rdb'
        else:
            self.rdb_filename = rdb_filename
        self.r.config_set('dbfilename', self.rdb_filename)
        logger.info(f'rdb filename: {self.rdb_filename}')

        self.r.xadd("graph_status", {'status': self.state[0]}) #status 1 means graph is running
        
        self.model["redis_host"] = self.host
        self.model["redis_port"] = self.port
        
        self.model["metadata"] = {}
        metadata = graph_dict['metadata']
        self.model["metadata"] = metadata
        
        self.model["nodes"] = {}
        self.r.xadd("graph_status", {'status': self.state[1]})  # status 2 means graph is parsing
        for n in nodes:
            bin_f = self.search_node_bin_file(n["module"],n["name"])
            if(os.path.exists(bin_f)):
                logger.info("Yaml and bin files exist in the path")
                logger.info("%s is a valid node...." % n["nickname"])
            else:
                logger.info("Bin files / executables do not exist in the path")
                logger.error("%s is not a valid node...." % n["nickname"])
                sys.exit(1)

            # Loading the nodes and graph into self.model dict
            self.model["nodes"][n["nickname"]] = {}
            self.model["nodes"][n["nickname"]].update(n)
            self.model["nodes"][n["nickname"]]["name"] = n["nickname"]
            self.model["nodes"][n["nickname"]]["binary"] = bin_f

        if "derivatives" in graph_dict:
            self.model["derivatives"] = {}
            derivatives = graph_dict['derivatives']
            for a in derivatives:
                a_name = list(a.keys())[0]
                a_values = a[a_name]
                self.model["derivatives"][a_name] = a_values

        self.r.xadd("graph_status", {'status': self.state[3]}) # status 3 means graph is parsed and running successfully
        model_pub = json.dumps(self.model)
        payload = {
            "data": model_pub
        }
        self.r.xadd("supergraph_stream",payload)
        logger.info("Supergraph Stream (Model) published successfully with payload..")
        self.r.xadd("graph_status", {'status': self.state[4]}) # status 4 means graph is running and supergraph is published


    ####### functions for the booting and stopping node #######
    def start_graph(self):
        ''' Start the graph '''
        current_state = self.r.xrevrange("graph_status",count = 1)
        current_graph_status = self.get_graph_status(current_state)
        logger.info("Current status of the graph is: %s" % current_graph_status)
        logger.info("Validation of the graph is successful")
        host = self.model["redis_host"]
        port = self.model["redis_port"]
        for node, node_info in self.model["nodes"].items():
            node_stream_name = node_info["nickname"]
            pid = os.fork() # forking the supervisor process
            self.r.xadd("graph_status", {'status': self.state[3]}) #status 3 means graph is parsed and running successfully
            if(pid > 0):
                try:
                    self.read_commands_from_redis()
                    logger.info("Parent process is running and waiting for commands from redis..")
                    self.parent = os.getpid()
                    self.children.append(pid)
                    logger.info(self.r.xread({str(node_stream_name+"_state"):"$"},count=1,block=5000))
                except signal.SIGCHLD:
                    signal(signal.SIGCHLD,callback = self.child_process_handler(node_stream_name))
            elif(pid < 0):
                logger.critical("Unable to create a child process")
                sys.exit(1)
            else:  # we are in a child process
                logger.info("Child process created with pid: %s" % os.getpid())
                binary = node_info["binary"]
                logger.info("Binary for %s is %s" % (node, binary))
                logger.info("Node Stream Name: %s" % node_stream_name)
                logger.info("Parent Running on: %d" % os.getppid())
                self.children.append(os.getpid())
                args = [
                    binary, '-n', node_stream_name, '-hs', host, '-p',
                    str(port)
                ]
                if 'run_priority' in node_info:  # if priority is specified
                    priority = node_info['run_priority']
                    if priority:  # if priority is not None or empty
                        chrt_args = ['chrt', '-f', str(int(priority))]
                        args = chrt_args + args
                try:
                    subprocess.run(args)
                except subprocess.CalledProcessError as e:
                    logger.info("Something wrong",e)
        # status 3 means graph is running and publishing data
        self.r.xadd("graph_status", {'status': self.state[3]})




    def stop_graph(self):
        '''
        Kills the child processes and stops the graph
        '''
        # Kill child processes (nodes)
        self.r.xadd("graph_status", {'status': self.state[5]})
        logger.debug(self.children)
        if(self.children):
            for i in range(len(self.children)):
                os.kill(self.children[i], signal.SIGINT)
                logger.info("Killed the child process with pid %d" % self.children[i])
            self.children = []


    def stop_graph_and_save_nwb(self):
        '''
        Stops the graph
        '''
        # Kill child processes (nodes)
        self.stop_graph()

        # Save rdb file
        if not os.path.exists(self.save_path_rdb):
            os.makedirs(self.save_path_rdb)
        self.r.config_set('dir',  self.save_path_rdb)
        logger.info(f"RDB save directory set to {self.save_path_rdb}")
        self.r.save()
        logger.info(f"RDB data saved to file: {self.rdb_filename}")

        # Generate NWB dataset
        p_nwb = subprocess.Popen(['python',
                            'derivatives/exportNWB/exportNWB.py',
                            self.save_path_rdb,
                            self.rdb_filename,
                            self.host,
                            str(self.port),
                            self.save_path_nwb], 
                            stdout=subprocess.PIPE)
        p_nwb.wait()

        # Flush database
        self.r.flushdb()

        # Set new rdb filename (to avoid overwriting what we just saved)
        self.rdb_filename =  'idle_' + datetime.now().strftime(r'%y%m%dT%H%M') + '.rdb'
        self.r.config_set('dbfilename', self.rdb_filename)
        logger.info(f"New RDB file name set to {self.rdb_filename}")        

        # New RDB, so need to reset graph status
        self.r.xadd("graph_status", {'status': self.state[5]})


    def terminate(self, sig, frame):
        logger.info('SIGINT received, Exiting')
        sys.exit(0)


    def parseCommands(self,command,file=None,rdb_filename=None):
        '''
        Parses the command and calls the appropriate function
        Args:
            command: command to be parsed
        '''

        if command == "startGraph" and file is not None:
            logger.info("Start graph command received with file")
            graph_dict = {}
            try:
                with open(file, 'r') as stream:
                    graph_dict = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.error(exc)
                sys.exit(1)
            self.load_graph(graph_dict,rdb_filename=rdb_filename)
            self.start_graph()
        elif command == "startGraph":
            logger.info("Start graph command received")
            self.start_graph()
        elif command == "stopGraph":
            logger.info("Stop graph command received")
            self.stop_graph()
        elif command == "stopGraphAndSaveNWB":
            logger.info("Stop graph and save NWB command received")
            self.stop_graph_and_save_nwb()
        else:
            logger.warning("Invalid command")

    def read_commands_from_redis(self):
        '''
        Reads the commands from redis and calls the appropriate function
        '''
        commands = {
        "startGraph": "",
        "stopGraph": "",
        "file": "",
        }
        if(self.r.ping()):
            self.r.xadd("supervisor_ipstream",commands)



def main():
    supervisor = Supervisor()
    while(True):
        cmd = supervisor.r.xread({"supervisor_ipstream":"$"},count=1,block=50000)
        if cmd:
            key,messages = cmd[0]
            last_id,data = messages[0]
            cmd = (data[b'commands']).decode("utf-8")
            if(len(data) == 2):
                file = data[b'file'].decode("utf-8")
                supervisor.parseCommands(cmd,file)
            else:
                supervisor.parseCommands(cmd)


if __name__ == "__main__":
    main()
