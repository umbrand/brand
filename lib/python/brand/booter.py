"""
Booter is a daemon that starts and stops nodes according to commands
sent by Supervisor
"""
import argparse
import coloredlogs
import json
import logging
import os
import psutil
import redis
import signal
import subprocess
import sys
import traceback

from threading import Event

from .derivative import RunDerivatives, RunDerivativeSet
from .exceptions import CommandError, DerivativeError, GraphError, NodeError
from .redis import RedisLoggingHandler

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
        self.derivative_threads = {}
        self.derivative_stop_events = {}
        # set the base directory as the current working directory
        self.brand_base_dir = os.getcwd()
        # connect to Redis
        self.r = redis.Redis(self.host, self.port, socket_connect_timeout=1)
        # add a Redis logging handler
        self.redis_log_handler = RedisLoggingHandler(self.r, f'booter_{self.machine}')
        self.logger.addHandler(self.redis_log_handler)
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
                f'{name} executable was not found at {filepath}',
                self.model['graph_name'],
                name)
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
            if 'machine' in cfg and cfg['machine'] == self.machine:
                # get paths to node executables
                filepath = self.get_node_executable(cfg['module'], cfg['name'])
                self.model['nodes'][node]['binary'] = filepath

        for deriv, cfg in self.model['derivatives'].items():
            if 'machine' in cfg and cfg['machine'] == self.machine:
                # verify the given filepath exists
                if not os.path.exists(cfg['filepath']):
                    raise DerivativeError('Derivative filepath does not exist',
                                          deriv,
                                          self.model['graph_name'])

        self.logger.info(f'Loaded graph with nodes: {node_names}')

    def start_graph(self):
        """
        Start the nodes in the graph that are assigned to this machine
        """
        host, port = self.model['redis_host'], self.model['redis_port']
        for node, cfg in self.model['nodes'].items():
            # specify defaults
            cfg.setdefault('root', True)
            # run the node if it is assigned to this machine
            if 'machine' in cfg and cfg['machine'] == self.machine:
                node_stream_name = cfg["nickname"]
                # build CLI command
                args = []
                if not cfg['root'] and 'SUDO_USER' in os.environ:
                    # run nodes as the current user, not root
                    args += [
                        'sudo', '-u', os.environ['SUDO_USER'], '-E', 'env',
                        f"PATH={os.environ['PATH']}"
                    ]
                args += [
                    cfg['binary'], '-n', node_stream_name, '-i', host, '-p',
                    str(port)
                ]
                # root permissions are needed to set real-time priority
                if 'run_priority' in cfg:  # if priority is specified
                    priority = cfg['run_priority']
                    if priority:  # if priority is not None or empty
                        chrt_args = ['chrt', '-f', str(int(priority))]
                        args = chrt_args + args
                if 'cpu_affinity' in cfg:  # if affinity is specified
                    affinity = cfg['cpu_affinity']
                    if affinity:  # if affinity is not None or empty
                        taskset_args = ['taskset', '-c', str(affinity)]
                        args = taskset_args + args
                p = subprocess.Popen(args)
                self.logger.debug(' '.join(args))
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
        '''
        Kills child processes
        '''

        def kill_proc_tree(pid, sig=signal.SIGTERM, include_parent=True):
            """
            Kill a process tree (including grandchildren) with signal "sig"
            """
            parent = psutil.Process(pid)
            children = parent.children(recursive=False)
            if include_parent:
                children.append(parent)
            for p in children:
                try:
                    p.send_signal(sig)
                except psutil.NoSuchProcess:
                    pass

        for node, proc in self.children.items():
            try:
                # check if process exists
                os.kill(proc.pid, 0)
            except OSError:
                self.logger.warning(f"'{node}' (pid: {proc.pid})"
                                    " isn't running and may have crashed")
                self.children[node] = None
            else:
                # process is running
                # send SIGINT
                kill_proc_tree(proc.pid, signal.SIGINT)
                try:
                    # check if it terminated
                    proc.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Could not stop '{node}' "
                                        f"(pid: {proc.pid}) using SIGINT")
                    # if not, send SIGKILL
                    kill_proc_tree(proc.pid, signal.SIGKILL)
                    try:
                        # check if it terminated
                        proc.communicate(timeout=15)
                    except subprocess.TimeoutExpired:
                        pass  # delay error message until after the loop
                    else:
                        self.logger.info(f"Killed '{node}' "
                                         f"(pid: {proc.pid}) using SIGKILL")
                        self.children[node] = None
                else:
                    self.logger.info(f"Stopped '{node}' "
                                     f"(pid: {proc.pid}) using SIGINT")
                    self.children[node] = None
        # remove killed processes from self.children
        self.children = {
            n: p
            for n, p in self.children.items() if p is not None
        }
        # raise an error if nodes are still running
        if self.children:
            running_nodes = [
                f'{node} ({p.pid})' for node, p in self.children.items()
            ]
            message = ', '.join(running_nodes)
            self.logger.exception('Could not kill these nodes: '
                                  f'{message}')
            
    def start_autorun_derivatives(self):
        '''
        Runs the autorun derivatives
        '''
        self.derivative_stop_events[f'booter_{self.machine}_autorun'] = Event()
        autorun_derivative_thread = RunDerivatives(
            machine=self.machine, 
            model=self.model,
            host=self.host,
            port=self.port,
            brand_base_dir=self.brand_base_dir,
            stop_event=self.derivative_stop_events[f'booter_{self.machine}_autorun'])
        autorun_derivative_thread.start()
        self.derivative_threads[f'booter_{self.machine}_autorun'] = autorun_derivative_thread

    def kill_autorun_derivatives(self):
        if f'booter_{self.machine}_autorun' in self.derivative_threads:
            self.derivative_stop_events[f'booter_{self.machine}_autorun'].set()
            del self.derivative_stop_events[f'booter_{self.machine}_autorun']
            del self.derivative_threads[f'booter_{self.machine}_autorun']
            self.logger.info(f"Autorun derivatives killed.")
        else:
            raise CommandError("Autorun derivatives not running.", f'booter {self.machine}', 'killAutorunDerivatives')
            
    def run_derivatives(self, derivative_names):
        '''
        Runs a list of derivatives
        '''

        # for later logging of method outcomes
        started_derivatives = []
        failed_derivatives = {}

        # loop through derivatives and start each if able
        for derivative in derivative_names:
            # only attempt to run derivatives specified for this machine
            if self.model['derivatives'][derivative]['machine'] == self.machine:
                # check if derivative is already running
                if derivative in self.derivative_threads:
                    if self.derivative_threads[derivative].is_alive():
                        failed_derivatives[derivative] = 'already running'
                # make sure derivative is not already running
                if derivative not in failed_derivatives:
                    # generate a stop event for this derivative
                    self.derivative_stop_events[derivative] = Event()
                    # start the derivative
                    derivative_thread = RunDerivativeSet(
                        machine=self.machine,
                        derivatives=[self.model['derivatives'][derivative]],
                        host=self.host,
                        port=self.port,
                        brand_base_dir=self.brand_base_dir,
                        stop_event=self.derivative_stop_events[derivative])
                    derivative_thread.start()
                    # add the derivative to the list of running derivatives
                    self.derivative_threads[derivative] = derivative_thread
                    started_derivatives.append(derivative)

        if started_derivatives:
            self.logger.info(f"Started derivative(s): {started_derivatives}")

        if failed_derivatives:
            raise CommandError(f"Derivative(s) failed to start: {failed_derivatives}", 'supervisor', 'runDerivative')

    def kill_derivatives(self, derivative_names):
        '''
        Kills a list of derivatives
        '''
        # for later logging of method outcomes
        killed_derivatives = []
        failed_derivatives = {}

        # loop through derivatives and kill each if able
        for derivative in derivative_names:
            # only kill derivatives on this machine
            if self.model['derivatives'][derivative]['machine'] == self.machine:
                # check if derivative is running
                if derivative in self.derivative_threads:
                    # set the stop event for this derivative
                    self.derivative_stop_events[derivative].set()
                    # clear derivative and event instances
                    del self.derivative_stop_events[derivative]
                    del self.derivative_threads[derivative]
                    killed_derivatives.append(derivative)
                else:
                    # derivative is not running
                    failed_derivatives[derivative] = 'not running'
        
        if killed_derivatives:
            self.logger.info(f"Killed derivative(s): {killed_derivatives}")
            
        if failed_derivatives:
            raise CommandError(f"Derivative(s) failed to kill: {failed_derivatives}", 'supervisor', 'killDerivative')

    def make(self, graph=None, node=None, derivative=None, module=None):
        '''
        Makes nodes and derivatives, defaults to all unless graph, node, or derivative is specified
        '''
        # Run make

        proc_cmd = ['make']

        if graph is not None:
            proc_cmd += [f'graph="{graph}"']

        if node is not None:
            proc_cmd += [f'node="{node}"']

        if derivative is not None:
            proc_cmd += [f'derivative="{derivative}"']

        if module is not None:
            proc_cmd += [f'module="{module}"']

        proc_cmd += [f'machine="{self.machine}"']

        p_make = subprocess.run(proc_cmd,
                                capture_output=True)

        if p_make.returncode == 0:
            self.r.xadd("booter_status", {"machine": self.machine, "status": "Make completed successfully"})
            self.logger.info(f"Make completed successfully")
        elif p_make.returncode > 0:
            raise CommandError(
                f"Make returned exit code {p_make.returncode}.",
                f'booter {self.machine}',
                'make',
                'STDOUT:\n' + p_make.stdout.decode('utf-8') + '\nSTDERR:\n' + p_make.stderr.decode('utf-8'))
        elif p_make.returncode < 0:
            self.logger.info(f"Make was halted during execution with return code {p_make.returncode}, {signal.Signals(-p_make.returncode).name}")

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
        elif command == 'make':
            graph = entry[b'graph'].decode('utf-8') if b'graph' in entry else None
            node = entry[b'node'].decode('utf-8') if b'node' in entry else None
            derivative = entry[b'derivative'].decode('utf-8') if b'derivative' in entry else None
            module = entry[b'module'].decode('utf-8') if b'module' in entry else None
            self.make(graph=graph, node=node, derivative=derivative, module=module)
        elif command == 'startAutorunDerivatives':
            self.start_autorun_derivatives()
        elif command == 'killAutorunDerivatives':
            self.kill_autorun_derivatives()
        elif command in ["runDerivative", "runDerivatives"]:
            if b'derivatives' in entry:
                derivatives = entry[b'derivatives']
            elif b'derivative' in entry:
                derivatives = entry[b'derivative']
            else:
                raise CommandError("runDerivative(s) command requires a 'derivative' or 'derivatives' key", 'supervisor', 'runDerivatives')

            derivatives = derivatives.decode('utf-8').split(',')
            self.run_derivatives(derivatives)
        elif command in ["killDerivative", "killDerivatives"]:
            if b'derivatives' in entry:
                derivatives = entry[b'derivatives']
            elif b'derivative' in entry:
                derivatives = entry[b'derivative']
            else:
                raise CommandError("killDerivative(s) command requires a 'derivative' or 'derivatives' key", 'supervisor', 'killDerivatives')
            
            derivatives = derivatives.decode('utf-8').split(',')
            self.kill_derivatives(derivatives)

    def run(self):
        """
        Listen for commands on the booter stream and execute them. Catch
        and log any exceptions encountered when executing commands.
        """
        entry_id = '$'
        self.logger.info('Listening for commands')
        self.r.xadd("booter_status", {"machine": self.machine, "status": "Listening for commands"})
        while True:

            for derivative in list(self.derivative_threads.keys()):
                if not self.derivative_threads[derivative].is_alive():
                    del self.derivative_threads[derivative]
                    del self.derivative_stop_events[derivative]
                    
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
                self.terminate()

            except (CommandError, DerivativeError, GraphError, NodeError) as exc:
                # if a node has an error, stop the graph and kill all nodes
                self.r.xadd("booter_status",
                    {'machine': self.machine,
                    'status': exc.__class__.__name__,
                    'message': str(exc),
                    'traceback': 'Booter ' + self.machine + ' ' + traceback.format_exc()})
                self.r.xadd("booter_status",
                    {'machine': self.machine, 'status': 'Listening for commands'})
                if exc is NodeError:
                    self.logger.error(f"Error with the {exc.node} node in the {exc.graph} graph")
                elif exc is GraphError:
                    self.logger.error(f"Error with the {exc.graph} graph")
                elif exc is DerivativeError:
                    self.logger.error(f"Error with the {exc.derivative} derivative in the {exc.graph} graph")
                elif exc is CommandError:
                    self.logger.error(f"Error with the {exc.command} command")
                self.logger.error(str(exc))

            except Exception as exc:
                self.r.xadd('booter_status',
                    {'machine': self.machine,
                    'status': 'Unhandled exception',
                    'message': str(exc),
                    'traceback': 'Booter ' + self.machine + ' ' + traceback.format_exc()})
                self.logger.exception(f'Could not execute command. {repr(exc)}')
                self.r.xadd("booter_status", {"machine": self.machine, "status": "Listening for commands"})

    def terminate(self, *args, **kwargs):
        """
        End this booter process when SIGINT is received
        """
        self.logger.info('SIGINT received, Exiting')

        # attempt to kill nodes
        try:
            self.kill_nodes()
        except Exception as exc:
            self.logger.warning(f"Could not kill nodes. Exiting anyway. {repr(exc)}")

        # attempt to kill derivatives
        try:
            for event in self.derivative_stop_events.values():
                event.set()
        except Exception as exc:
            self.logger.warning(f"Could not kill derivatives. Exiting anyway. {repr(exc)}")

        # attempt to post an exit message to Redis
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