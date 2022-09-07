"""
Booter is a daemon that starts and stops nodes according to commands
sent by Supervisor
"""
import argparse
import json
import logging
import os
import signal
import subprocess
import sys

import coloredlogs
import redis

from brand import (GraphError, NodeError, RedisError)

DEFAULT_REDIS_IP = '127.0.0.1'
DEFAULT_REDIS_PORT = 6379


class Booter():
    """
    Booter is a class for starting and stopping nodes
    
    Attributes
    ----------
    model : dict
        Configuration set that defines the current supergraph
    children : dict
        Child processes that are currently running. Keys are node nicknames
        and values are subprocess.Popen instances for each running node.
    """

    def __init__(self,
                 machine,
                 host=DEFAULT_REDIS_IP,
                 port=DEFAULT_REDIS_PORT,
                 log_level=logging.INFO) -> None:
        """
        Booter starts and stops nodes according to commands received from
        the Supervisor via Redis

        Parameters
        ----------
        machine : str
            Unique name for this machine. To start a node with this Booter
            instance, you must specify a 'machine' parameter that matches the
            'machine' parameter for this Booter instance.
        host : str, optional
            Redis IP address, by default DEFAULT_REDIS_IP
        port : int, optional
            Redis port, by default DEFAULT_REDIS_PORT
        log_level : int, optional
            Logging level, by default logging.INFO
        """
        self.host = host
        self.port = port
        self.machine = machine
        # make a logger
        self.logger = logging.getLogger(f'booter-{self.machine}')
        coloredlogs.install(level=log_level, logger=self.logger)
        # instatiate run variables
        self.model = {}
        self.children = {}
        # set the base directory as the current working directory
        self.brand_base_dir = os.getcwd()
        # connect to Redis
        self.r = redis.Redis(self.host, self.port, socket_connect_timeout=1)
        # register signal handler
        signal.signal(signal.SIGINT, self.terminate)

    def get_node_executable(self, module, name):
        """
        Get the path to the node executable

        Parameters
        ----------
        module : str
            Path to the module in which the node is located
        name : str
            Name of the node

        Returns
        -------
        filepath : str
            Absolute path to the node executable
        """
        filepath = os.path.join(self.brand_base_dir, module, 'nodes', name,
                                f'{name}.bin')
        filepath = os.path.abspath(filepath)
        if not os.path.exists(filepath):
            raise NodeError(
                self.model['graph_name'],
                name,
                f'{name} executable was not found at {filepath}')
        return filepath

    def load_graph(self, graph: dict):
        """
        Load a new supergraph into Booter

        Parameters
        ----------
        graph : dict
            Dictionary containing the supergraph parameters
        """
        # load node information
        self.model = graph
        node_names = list(self.model['nodes'])
        for node, cfg in self.model['nodes'].items():
            # get paths to node executables
            filepath = self.get_node_executable(cfg['module'], cfg['name'])
            self.model['nodes'][node]['binary'] = filepath
        self.logger.info(f'Loaded graph with nodes: {node_names}')

    def start_graph(self):
        """
        Start the nodes in the graph that are assigned to this machine
        """
        host, port = self.model['redis_host'], self.model['redis_port']
        for node, cfg in self.model['nodes'].items():
            if 'machine' in cfg and cfg['machine'] == self.machine:
                node_stream_name = cfg["nickname"]
                args = [
                    cfg['binary'], '-n', node_stream_name, '-i', host, '-p',
                    str(port)
                ]
                if 'run_priority' in cfg:  # if priority is specified
                    priority = cfg['run_priority']
                    if priority:  # if priority is not None or empty
                        chrt_args = ['chrt', '-f', str(int(priority))]
                        args = chrt_args + args
                p = subprocess.Popen(args)
                self.children[node] = p
        
        self.r.xadd("booter_status", {"machine": self.machine, "status": f"{self.model['graph_name']} graph started successfully"})

    def stop_graph(self):
        """
        Stop the nodes on this machine that correspond to the running graph
        """
        self.kill_nodes()
        if 'graph_name' in self.model:
            graph = self.model['graph_name']
        else:
            graph = 'None'
        self.r.xadd("booter_status", {"machine": self.machine, "status": f"{graph} graph stopped successfully"})
    
    def kill_nodes(self):
        """
        Kills the nodes running on this machine
        """
        for node, p in self.children.items():
            p.send_signal(signal.SIGINT)
            try:
                p.wait(timeout=15)
                self.logger.info(f'Killed the {node} process with pid {p.pid}')
            except Exception:
                self.logger.exception(f'Could not kill the {node} node with'
                                      f' pid {p.pid}')
        self.children = {}

    def parse_command(self, entry):
        """
        Parse an entry from the 'booter' stream and run the corresponding
        command

        Parameters
        ----------
        entry : dict
            An entry from the 'booter' stream containing a 'command' key
        """
        command = entry[b'command'].decode()
        if command == 'startGraph':
            graph_dict = json.loads(entry[b'graph'])
            self.load_graph(graph_dict)
            self.start_graph()
        elif command == 'stopGraph':
            self.stop_graph()

    def run(self):
        """
        Listen for commands on the booter stream and execute them. Catch
        and log any exceptions encountered when executing commands.
        """
        entry_id = '$'
        self.logger.info('Listening for commands')
        self.r.xadd("booter_status", {"machine": self.machine, "status": "Listening for commands"})
        while True:
            try:
                streams = self.r.xread({'booter': entry_id},
                                       block=5000,
                                       count=1)
                if streams:
                    _, stream_data = streams[0]
                    entry_id, entry_data = stream_data[0]
                    command = entry_data[b'command'].decode()
                    self.logger.info(f'Received {command} command')
                    self.parse_command(entry_data)
            except redis.exceptions.ConnectionError as exc:
                self.logger.error('Could not connect to Redis: ' + repr(exc))
                sys.exit(0)
            except NodeError as exc:
                # if a node has an error, stop the graph and kill all nodes
                self.r.xadd("booter_status",
                    {'machine': self.machine,
                    'status': 'graph failed',
                    'message': repr(exc)})
                self.kill_nodes()
                self.r.xadd("booter_status",
                    {'machine': self.machine, 'status': 'Listening for commands'})
                self.logger.error(f"Error with the {exc.node_nickname} node in the {exc.graph_name} graph")
                self.logger.error(exc.err_str)
            except Exception as exc:
                self.r.xadd("booter_status", {"machine": self.machine, "status": "Unhandled exception", "message": repr(exc)})
                self.logger.exception(f'Could not execute command. {repr(exc)}')
                self.r.xadd("booter_status", {"machine": self.machine, "status": "Listening for commands"})

    def terminate(self, *args, **kwargs):
        """
        End this booter process when SIGINT is received
        """
        self.logger.info('SIGINT received, Exiting')
        try:
            self.r.xadd("booter_status", {"machine": self.machine, "status": "SIGINT received, Exiting"})
        except Exception as exc:
            self.logger.warning(f"Could not write exit message to Redis. Exiting anyway. {repr(exc)}")
        sys.exit(0)


def parse_booter_args():
    """
    Parse command-line arguments for Booter

    Returns
    -------
    args : Namespace
        Booter arguments
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("-m",
                    "--machine",
                    required=True,
                    type=str,
                    help="machine on which this booter is running")
    ap.add_argument("-i",
                    "--host",
                    required=False,
                    type=str,
                    default=DEFAULT_REDIS_IP,
                    help="ip address of the redis server"
                    f" (default: {DEFAULT_REDIS_IP})")
    ap.add_argument("-p",
                    "--port",
                    required=False,
                    type=int,
                    default=DEFAULT_REDIS_PORT,
                    help="port of the redis server"
                    f" (default: {DEFAULT_REDIS_PORT})")
    ap.add_argument("-l",
                    "--log-level",
                    default=logging.INFO,
                    type=lambda x: getattr(logging, x),
                    help="Configure the logging level")
    args = ap.parse_args()
    return args


if __name__ == '__main__':
    # parse command line arguments
    args = parse_booter_args()
    kwargs = vars(args)
    # Run Booter
    booter = Booter(**kwargs)
    booter.run()
