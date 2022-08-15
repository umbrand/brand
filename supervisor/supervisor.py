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
import time

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
        self.BRAND_MOD_DIR = os.path.join(self.BRAND_BASE_DIR,'../brand-modules/') # path to the brand modules directory

        self.save_path = self.BRAND_BASE_DIR
        self.save_path_rdb = self.save_path

        self.state = ("initialized", "parsing", "graph failed", "running",
                      "published", "stopped/not initialized")

        self.graph_file = None
        self.redis_pid = None

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
        ap.add_argument("-s", "--socket", required=False, help="unix socket to bind redis server to")
        ap.add_argument("-c", "--cfg", required=False, help="cfg file for redis server")
        ap.add_argument("-m", "--machine", type=str, required=False, help="machine on which this supervisor is running")
        ap.add_argument("-r", "--redis-priority", type=int, required=False, help="priority to use for the redis server")
        ap.add_argument("-a", "--redis-affinity", type=str, required=False, help="cpu affinity to use for the redis server")
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

        self.unixsocket = args.socket
        if self.unixsocket is not None:
            self.redis_args += ['--unixsocket', self.unixsocket]

        self.machine = args.machine
        self.redis_priority = args.redis_priority
        self.redis_affinity = args.redis_affinity

        self.graph_file = args.graph
        graph_dict = {}
        if self.graph_file is not None:
            try:
                with open(args.graph, 'r') as stream:
                    graph_dict = yaml.safe_load(stream)
                    graph_dict['graph_name'] = os.path.splitext(os.path.split(args.graph)[-1])[0]
            except yaml.YAMLError as exc:
                logger.error("Error in parsing the graph file "+str(exc))
                sys.exit(1)
            logger.info("Graph file parsed successfully")
        return graph_dict


    def kill_redis_server(self):
        '''
        Kills the redis server
        '''
        logger.info("Killing the redis server")
        try:
            logger.info("PID of the redis server: %s" % self.redis_pid)
            if self.redis_pid is not None:
                os.kill(int(self.redis_pid), signal.SIGTERM)
                logger.info("Redis server killed")
            else:
                logger.info("No redis server found")
        except Exception as e:
            logger.error("Error in killing the redis server"+str(e))



    def search_node_bin_file(self,module,name)->str:
        ''' Search the node bin/exec file and return the bin/exec file path 
        Args:
            module: module name
            name : node name
        '''

        directory = [os.path.join(self.BRAND_BASE_DIR, module, "nodes", name)]
        bin_f = None

        for dir in directory:
            for file in os.listdir(dir):
                    if file.startswith(name) and (file.endswith(".bin") or file.endswith(".out")):
                        bin_file = os.path.join(dir, file)
                        logger.info("bin/exec file path: %s" % bin_file)
                        bin_f = bin_file
                        return bin_f
        if(bin_f is None):
            logger.error(f"No bin/exec file found for the node {name}. Try running make in the root directory.")
            logger.info("Closing Redis and stopping the supervisor.")
            #self.r.flushdb()
            self.kill_redis_server()
            sys.exit(1)


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
        if self.redis_priority:
            chrt_args = ['chrt', '-f', f'{self.redis_priority :d}']
            redis_command = chrt_args + redis_command
        if self.redis_affinity:
            redis_command = ['taskset', '-c', self.redis_affinity
                             ] + redis_command
        logger.info('Starting redis: ' + ' '.join(redis_command))
        # get a process name by psutil
        proc = subprocess.Popen(redis_command)
        self.redis_pid = proc.pid
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

    def get_save_path(self, graph_dict):
        """
        Get the path where the RDB and NWB files should be saved
        Parameters
        ----------
        graph_dict : dict
            Dictionary containing the supergraph parameters
        Returns
        -------
        save_path : str
            Path where data should be saved
        """
        # Check if the participant file exists
        has_participant_file = (
            'metadata' in graph_dict
            and 'participant_file' in graph_dict['metadata']
            and os.path.exists(graph_dict['metadata']['participant_file']))

        # Get participant and session info
        if has_participant_file:
            with open(graph_dict['metadata']['participant_file'], 'r') as f:
                participant_info = yaml.safe_load(f)
            participant_id = participant_info['metadata']['participant_id']
        elif 'metadata' in graph_dict and 'participant_id' in graph_dict['metadata']:
            participant_id = graph_dict['metadata']['participant_id']
        else:
            participant_id = 0

        # Make paths for saving files
        session_str = datetime.today().strftime(r'%Y-%m-%d')
        session_id = f'{session_str}'
        save_path = os.path.join(self.BRAND_BASE_DIR, '..', 'Data',
                                 str(participant_id), session_id, 'RawData')
        save_path = os.path.abspath(save_path)
        return save_path

    def load_graph(self,graph_dict,rdb_filename=None):
        ''' Running logic for the supervisor graph, establishes a redis connection on specified host & port  
        Args:
            graph_dict: graph dictionary
        '''
        nodes = graph_dict['nodes']

        self.graph_name = graph_dict['graph_name']

        self.r.xadd("graph_status", {'status': self.state[0]}) #status 1 means graph is running

        self.model["redis_host"] = self.host
        self.model["redis_port"] = self.port
        self.model["graph_name"] = self.graph_name

        # Set rdb save directory
        self.save_path = self.get_save_path(graph_dict)
        self.save_path_rdb = os.path.join(self.save_path, 'RDB')
        if not os.path.exists(self.save_path_rdb):
            os.makedirs(self.save_path_rdb)
        self.r.config_set('dir', self.save_path_rdb)
        logger.info(f"RDB save directory set to {self.save_path_rdb}")

        # Set rdb filename
        if rdb_filename is None:
            self.rdb_filename =  self.save_path.split(os.path.sep)[-3] + '_' + datetime.now().strftime(r'%y%m%dT%H%M') + '_' + self.graph_name + '.rdb'
        else:
            self.rdb_filename = rdb_filename
        self.r.config_set('dbfilename', self.rdb_filename)
        logger.info(f'rdb filename: {self.rdb_filename}')

        # Load node information
        self.model["nodes"] = {}
        self.r.xadd("graph_status", {'status': self.state[1]})  # status 2 means graph is parsing

        # catch key errors for nodes that are not in the graph
        try:
            for n in nodes:
                bin_f = self.search_node_bin_file(n["module"],n["name"])
                if bin_f is not None:
                    logger.info("%s is a valid node...." % n["nickname"])
                    # Check for duplicate nicknames
                    if n["nickname"] in self.model["nodes"]:
                        logger.error("Duplicate node nickname found: %s. Rename the nicknames in the graph YAML file." % n["nickname"])
                        logger.info("Stopping the graph")
                        self.stop_graph()
                        return
                    # Loading the nodes and graph into self.model dict
                    self.model["nodes"][n["nickname"]] = {}
                    self.model["nodes"][n["nickname"]].update(n)
                    self.model["nodes"][n["nickname"]]["binary"] = bin_f

            if "derivatives" in graph_dict:
                self.model["derivatives"] = {}
                derivatives = graph_dict['derivatives']
                for a in derivatives:
                    a_name = list(a.keys())[0]
                    a_values = a[a_name]
                    self.model["derivatives"][a_name] = a_values

        except KeyError as e:
            logger.error("KeyError: %s field missing in graph YAML" % e)
            logger.info("Closing Redis and stopping the supervisor.")
            #self.r.flushdb()
            self.kill_redis_server()
            sys.exit(1)

        self.r.xadd("graph_status", {'status': self.state[3]}) # status 3 means graph is parsed and running successfully
        model_pub = json.dumps(self.model)
        payload = {
            "data": model_pub
        }
        self.r.xadd("supergraph_stream",payload)
        logger.info("Supergraph Stream (Model) published successfully with payload..")
        self.r.xadd("graph_status", {'status': self.state[4]}) # status 4 means graph is running and supergraph is published


    def start_graph(self):
        ''' Start the graph '''
        self.r.xadd('booter', {
            'command': 'startGraph',
            'graph': json.dumps(self.model)
        })
        current_state = self.r.xrevrange("graph_status", count=1)
        current_graph_status = self.get_graph_status(current_state)
        logger.info("Current status of the graph is: %s" % current_graph_status)
        logger.info("Validation of the graph is successful")
        host = self.model["redis_host"]
        port = self.model["redis_port"]
        for node, node_info in self.model["nodes"].items():
            node_stream_name = node_info["nickname"]
            if ('machine' not in node_info
                    or node_info["machine"] == self.machine):
                binary = node_info["binary"]
                logger.info("Binary for %s is %s" % (node,binary))
                logger.info("Node Stream Name: %s" % node_stream_name)
                args = [binary, '-n', node_stream_name]
                args += ['-i', host, '-p', str(port)]
                if self.unixsocket:
                    args += ['-s', self.unixsocket]
                if 'run_priority' in node_info:  # if priority is specified
                    priority = node_info['run_priority']
                    if priority:  # if priority is not None or empty
                        chrt_args = ['chrt', '-f', str(int(priority))]
                        args = chrt_args + args
                if 'cpu_affinity' in node_info:  # if affinity is specified
                    affinity = node_info['cpu_affinity']
                    if affinity:  # if affinity is not None or empty
                        taskset_args = ['taskset', '-c', str(affinity)]
                        args = taskset_args + args
                proc = subprocess.Popen(args)
                logger.info("Child process created with pid: %s" % proc.pid)
                self.r.xadd("graph_status", {'status': self.state[3]})
                logger.info("Parent process is running and waiting for commands from redis..")
                self.parent = os.getpid()
                logger.info("Parent Running on: %d" % os.getppid())
                self.children.append(proc.pid)
                logger.info(self.r.xread({str(node_stream_name+"_state"):"$"},count=1,block=5000))
        # status 3 means graph is running and publishing data
        self.r.xadd("graph_status", {'status': self.state[3]})

    def stop_graph(self):
        '''
        Kills the child processes and stops the graph
        '''
        self.r.xadd('booter', {'command': 'stopGraph'})
        # Kill child processes (nodes)
        self.r.xadd("graph_status", {'status': self.state[5]})
        logger.debug(self.children)
        if(self.children):
            for i in range(len(self.children)):
                try: 
                    # check if process exists 
                    os.kill(self.children[i], 0)
                except OSError:
                    logger.warning(f"Child process with pid {self.children[i]} isn't running (may have crashed)")
                else:
                    os.kill(self.children[i], signal.SIGINT)
                    logger.info("Killed the child process with pid %d" % self.children[i])
            self.children = []
        else:
            logger.info("No child processes to kill")


    def stop_graph_and_save_nwb(self):
        '''
        Stops the graph
        '''
        # Kill child processes (nodes)
        self.stop_graph()

        # Make path for saving NWB file
        save_path_nwb = os.path.join(self.save_path, 'NWB')
        # Save rdb file
        self.r.save()
        logger.info(f"RDB data saved to file: {self.rdb_filename}")

        # Generate NWB dataset
        p_nwb = subprocess.Popen(['python',
                            'derivatives/exportNWB/exportNWB.py',
                            self.rdb_filename,
                            self.host,
                            str(self.port),
                            save_path_nwb])
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

    def parseCommands(self, command, file=None, rdb_filename=None, graph=None):
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
                    graph_dict['graph_name'] = os.path.splitext(os.path.split(file)[-1])[0]
            except yaml.YAMLError as exc:
                logger.error(exc)
                logger.info("Closing Redis and stopping the supervisor.")
                #self.r.flushdb()
                self.kill_redis_server()
                sys.exit(1)
            self.load_graph(graph_dict,rdb_filename=rdb_filename)
            self.start_graph()
        elif command == "startGraph" and graph is not None:
            logger.info("Start graph command received with graph dict")
            self.load_graph(graph)
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


def main():
    supervisor = Supervisor()
    last_id = '$'
    while(True):
        cmd = supervisor.r.xread({"supervisor_ipstream": last_id},
                                 count=1,
                                 block=50000)
        if cmd:
            key,messages = cmd[0]
            last_id,data = messages[0]
            cmd = (data[b'commands']).decode("utf-8")

            if b'rdb_filename' in data:
                rdb_filename = data[b'rdb_filename'].decode("utf-8")
            else:
                rdb_filename = None

            if b'file' in data:
                file = data[b'file'].decode("utf-8")
                supervisor.parseCommands(cmd, file=file, rdb_filename=rdb_filename)
            elif b'graph' in data:
                graph = json.loads(data[b'graph'])
                supervisor.parseCommands(cmd, graph=graph, rdb_filename=rdb_filename)
            else:
                supervisor.parseCommands(cmd)


if __name__ == "__main__":
    main()
