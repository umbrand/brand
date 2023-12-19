# BRAND derivative template
# Author: Brandon Jacques, Sam Nason-Tomaszewski
# Adapted from code by: David Brandman and Kushant Patel

import logging
import os
import signal
import subprocess
import sys
import time

from redis import Redis

from threading import Event, Thread

from .exceptions import DerivativeError
from .redis import RedisLoggingHandler

# EXAMPLE DERIVATIVE YAML CONFIGS, BOTH WORK. 

#   - filename:     deriv.py
#     nickname:     this_derivative
#     name:         derivative_one
#     module:       ../brand-modules/npl-davis
#     machine:      *BRAND_MACHINE_NAME
#     run_priority:               99
#     cpu_affinity:               8-10
#     parameters:
#       log:                    INFO

#  OR

#   - full_path:    ../brand-modules/npl-davis/derivatives/brainToText/deriv.py
#     nickname:     this_derivative
#     machine:      *BRAND_MACHINE_NAME
#     run_priority:               99
#     cpu_affinity:               8-10
#     parameters:
#       log:                    INFO

DERIVATIVES_STATUS_STREAM = "derivatives_status"
CHECK_WAIT_TIME = .02

class RunDerivatives(Thread):

    def __init__(self, 
                 machine,
                 model,
                 host,
                 port,
                 brand_base_dir,
                 stop_event
                 ):
        self.nickname = "derivative_runner"

        self.step = -1
        self.machine = machine
        self.model = model

        self.redis_host = host
        self.redis_port = port
        self.redis_conn = self.connect_to_redis()

        self.brand_base_dir = brand_base_dir

        self.stop_event = stop_event

        self.failure_state = False

        self.current_thread = None

        # Configure logging.
        logging.basicConfig(format=f'[{self.nickname} step {self.step}] %(levelname)s: %(message)s',
                            level=logging.INFO)

        # Also send logs to Redis.
        self.redis_log_handler = RedisLoggingHandler(
            self.redis_conn, self.nickname
        )
        logging.getLogger().addHandler(self.redis_log_handler)

    def set_model(self, model):
        """Setter for model"""
        self.model = model
        self.get_steps()

    def get_steps(self, model=None):
        """Sets the total number of steps. 
        Paramters
        ---------
        model: dict
            A dictionary containing the current supergraph.

        Returns
        -------
        steps: list
            A list containing all the step numbers in order. """
        
        if model is None:
            model = self.model

        if (self.steps is not None):
            steps = []
            for deriv in model['derivatives']:
                if ('autorun_step' in deriv) and (deriv['autorun_step'] not in steps):
                    steps.append(deriv['autorun_step'])
                elif ('autorun_step' not in deriv) and (-1 not in steps):
                    steps.append(-1)

            steps.sort()
            self.steps = steps
        
        logging.info(f'Steps for Derivatives on {self.machine} are [{self.steps}]')
        return self.steps

    def run(self):
        """Runs the thread. Gets steps, creates a new thread for each step."""
        # Sets self.steps and sorts it.
        self.get_steps()

        for step in self.steps:
            self.step = step
            logging.info(f"Starting RunDerivativeStep {self.step}.")
            self.child_stop_event = Event()
            self.current_thread = RunDerivativeStep(
                machine=self.machine, 
                model=self.model,
                step=self.step,
                brand_base_dir=self.brand_base_dir,
                stop_event=self.child_stop_event)
            self.current_thread.start()
            if self.step > -1:
                # Wait for this step to finish.

                while self.current_thread.is_alive():
                    
                    # set by parent supervisor or booter
                    if self.stop_event.is_set():
                        self.kill_child_processes()
                        break

                    time.sleep(CHECK_WAIT_TIME)

                # Check if thread failed on finish, or if we were stopped early. 
                if self.current_thread.failure_state or self.failure_state:
                    self.kill_child_processes()
                    break
            else:
                continue

        logging.info(f"Derivative steps finished {'successfully' if not self.failure_state else 'in an error.'}")

    def report_future_failure(self, step=-1):
        """Report the failure to start for all derivatives in future steps."""
        end_timestamp = time.monotonic()
        
        for deriv in self.model['derivatives']:
            # Only report the error for the autorun set to True derivatives 
            # on this machine. 
            if deriv['autorun'] and (deriv['machine'] == self.machine):
                if (deriv['autorun_step'] > step):
                    nickname = deriv['nickname']
                    logging.warning(f"Previous step failed, derivative {nickname} never started.")
                    self.failure_state = True
                    self.redis_conn.xadd(
                        DERIVATIVES_STATUS_STREAM,
                        {
                            "nickname": nickname,
                            "status": "completed",
                            "success": 0,
                            "returncode": -1,
                            "stderr": "Never Started, Previous step errored.",
                            "timestamp": end_timestamp,
                        },
                    )

    def kill_child_processes(self):
        """Kills all child processes."""
        if self.current_thread is not None:
            self.child_stop_event.set()
            self.report_future_failure(step=self.step)
            self.failure_state = True

    def connect_to_redis(self):
        """
        Connect to redis, and add an initial entry to indicate this node successfully
        initialized.

        :return redis.Redis:
        """

        # Attempt to connect to redis.
        try:
            redis_conn = Redis(self.redis_host, self.redis_port, retry_on_timeout=True)
            print(
                f"[{self.nickname}] connected to redis with host: {self.redis_host}, "
                f"port: {self.redis_port}"
            )
        except ConnectionError as e:
            print(f"[{self.nickname}] unable to connect to redis. Error: {e}")
            self.failure_state = True
            sys.exit(1)

        return redis_conn

    def terminate(self, sig, frame):
        """
        Allow this node to clean up before it is killed.

        :param sig: Unused. Only there to satisfy built-in func signature.
        :param frame: Unused. Only there to satisfy built-in func signature.
        """
        logging.info("SIGINT received, Exiting")
        
        self.kill_child_processes()
        sys.exit(0)


class RunDerivativeStep(Thread):

    def __init__(self, 
                 machine,
                 model,
                 host,
                 port,
                 brand_base_dir,
                 stop_event,
                 step=0) -> None:
        """Run all derivatives in a step then start the next step.
        
        Parameters
        ----------
        
        machine: str
            Which Machine the process is being run on. 
        host: str
            Redis IP address
        port: int
            Redis port number
        log_level: str
            How much logging you want from this. 
        step: int 
            The current step number.
        cont: bool (default = True)
            Whether or not to start the next step automatically. This is 
            primarily here for when you might want to run a particular step 
            outside of the normal autorun. 
        failure_state: bool (default = False)
            Whether the previous step failed. 
        """
        self.nickname = 'derivative_step_runner'

        self.machine = machine
        self.model = model
        self.brand_base_dir = brand_base_dir

        self.redis_host = host
        self.redis_port = port 
        # Connect to redis.
        self.redis_conn = self.connect_to_redis()

        # get latest Redis ID in DERIVATIVES_STATUS_STREAM
        latest_entry = self.redis_conn.xrevrange(DERIVATIVES_STATUS_STREAM, '+', '-', count=1)
        if len(latest_entry) > 0:
            self.latest_id = latest_entry[0][0]
        else:
            self.latest_id = 0

        self.step = step

        self.running_children = {}
        self.finished_children = {}

        self.failure_state = False

        self.stop_event = stop_event

        signal.signal(signal.SIGINT, self.terminate)

    def connect_to_redis(self):
        """
        Connect to redis, and add an initial entry to indicate this node successfully
        initialized.

        :return redis.Redis:
        """

        # Attempt to connect to redis.
        try:
            redis_conn = Redis(self.redis_host, self.redis_port, retry_on_timeout=True)
            print(
                f"[{self.nickname}] connected to redis with host: {self.redis_host}, "
                f"port: {self.redis_port}"
            )
        except ConnectionError as e:
            print(f"[{self.nickname}] unable to connect to redis. Error: {e}")
            sys.exit(1)

        return redis_conn

    def start_derivative(self, deriv_info):

        nickname = deriv_info['nickname']

        if 'full_path' in deriv_info:
            full_path = deriv_info['full_path']
        else:
            name = deriv_info['name']
            filename = deriv_info['filename']
            module = deriv_info['module']
            full_path = os.path.join(
                self.brand_base_dir, module, "derivatives", name, filename
                )
        
        if '.py' in full_path:
            cmd = "python " + full_path
        elif '.bin' in full_path:
            cmd = "./" + full_path
        elif open(full_path,'r').readline()[:2] == "#!":
            cmd = "./" + full_path
        elif open(full_path,'r').readline()[:2] != "#!":
            logging.error(
                f"Derivative {nickname} is not Python or a Bin, nor does it "
                f"contain a shebang (#!) to let the OS know how to run it. "
                f"The derivative will not be started."
                )
            self.redis_conn.xadd(
                DERIVATIVES_STATUS_STREAM,
                {
                    "nickname": nickname,
                    "status": "completed",
                    "success": 0,
                    "returncode": -1,
                    "stderr": -1,
                    "timestamp": -1,
                },
            )
            return None
        
        # Build the actual args to the command. 
        args = [cmd, '-n', nickname]
        args += ['-i', self.redis_host, '-p', str(self.redis_port)]    
        # Add in the args about controlling priortiy and affinity.
        if 'run_priority' in deriv_info:  # if priority is specified
            priority = deriv_info['run_priority']
            if priority:  # if priority is not None or empty
                chrt_args = ['chrt', '-f', str(int(priority))]
                args = chrt_args + args
        if 'cpu_affinity' in deriv_info:  # if affinity is specified
            affinity = deriv_info['cpu_affinity']
            if affinity:  # if affinity is not None or empty
                taskset_args = ['taskset', '-c', str(affinity)]
                args = taskset_args + args
        # You can specify a derivative to start after some short delay even 
        # within a step (doesn't overload the CPU maybe). 
        if 'delay_sec' in deriv_info:
            delay_sec = deriv_info['delay_sec']
            delay_args = ['sleep', delay_sec, "&&"]
        else:
            delay_sec = None
            delay_args = []
        args = delay_args + args

        delay_msg = (
            f"in {delay_sec} seconds " if delay_sec is not None else ""
        )
        logging.info(f"Starting derivative {nickname} {delay_msg}...")

        proc = subprocess.Popen(args)
        start_timestamp = time.monotonic()

        self.redis_conn.xadd(
            DERIVATIVES_STATUS_STREAM,
            {
                "nickname": nickname,
                "status": "running",
                "timestamp": start_timestamp,
            },
        )

        return proc
    
    def wait_for_children(self):

        while len(self.running_children) > 0: 

            if self.stop_event.is_set():
                self.failure_state = True
                self.kill_child_processes()
                break

            # Iterate through a copy of the list, keys are nicknames
            for nickname in self.running_children.copy():
                # grab the proc for that nickname
                proc = self.running_children[nickname]
                
                if proc.pid not in self.finished_children:
                    returncode = proc.poll()
                    if returncode is not None:
                        end_timestamp = time.monotonic()

                        # Remove that nickname from the list. 
                        del self.running_children[nickname]

                        # Add it to the finished_children_list.
                        self.finished_children[nickname] = proc
                        
                        # Grab output of the process.
                        stdout, stderr = proc.communicate()
                        
                        # Send it out to redis. 
                        if returncode == 0:
                            logging.info(f"Derivative {nickname} completed successfully.")
                            self.redis_conn.xadd(
                                DERIVATIVES_STATUS_STREAM,
                                {
                                    "nickname": nickname,
                                    "status": "completed",
                                    "success": 1,
                                    "timestamp": end_timestamp,
                                },
                            )
                        else:
                            logging.error(f"Derivative {nickname} errored with code {returncode}.")
                            logging.error(stderr)
                            self.failure_state = True
                            self.redis_conn.xadd(
                                DERIVATIVES_STATUS_STREAM,
                                {
                                    "nickname": nickname,
                                    "status": "completed",
                                    "success": 0,
                                    "returncode": returncode,
                                    "stderr": stderr,
                                    "timestamp": end_timestamp,
                                },
                            )
            # Let some time pass as the derivatives run.
            time.sleep(CHECK_WAIT_TIME)

    def kill_child_processes(self):
        for nickname in self.running_children.copy():
            proc = self.running_children[nickname]
            proc.kill()
            returncode = proc.poll()
            logging.error(f"Derivative {nickname} was killed early.")
            self.failure_state = True
            self.redis_conn.xadd(
                DERIVATIVES_STATUS_STREAM,
                {
                    "nickname": nickname,
                    "status": "completed",
                    "success": 0,
                    "returncode": returncode,
                    "stderr": "Early Termination.",
                    "timestamp": time.monotonic(),
                },
            )
            del self.running_children[nickname]
            self.finished_children[nickname] = proc

    def start_current_step(self):
        for deriv in self.model['derivatives']:

            # Only try to run the derivatives in the assigned step0 
            if 'autorun_step' in deriv and deriv['autorun_step'] == self.step and (deriv['machine'] == self.machine):
                    
                proc = self.start_derivative(deriv)
                if proc is not None:
                    self.running_children[deriv['nickname']] = proc

    def check_all_derivatives(self):
        """Check that all derivatives in this step have finished,
        including those on other booters."""

        step_derivatives = [deriv
                            for deriv in self.model['derivatives']
                                if 'autorun_step' in deriv
                                    and deriv['autorun_step'] == self.step]

        while step_derivatives:
            derivative_status = self.redis_conn.xread(
                {DERIVATIVES_STATUS_STREAM: self.latest_id},
                block=0
            )
            for entry in derivative_status[0][1]:
                nickname = entry[1][b'nickname'].decode('utf-8')
                if nickname in step_derivatives:
                    # if the derivative is completed, remove it from the list
                    if entry[1][b'status'] == b'completed':
                        step_derivatives.remove(nickname)


    def run(self):
        # start all the derivatives
        self.start_current_step()

        self.wait_for_children()

        # check that all derivatives on all booters
        # are finished before exiting the step
        self.check_all_derivatives()

        # Close up process.
        logging.info(f"Step {self.step} {'Failed' if self.failure_state else 'Completed'}.")
        self.redis_conn.close()

    def terminate(self, sig, frame):
        """
        Allow this node to clean up before it is killed.

        :param sig: Unused. Only there to satisfy built-in func signature.
        :param frame: Unused. Only there to satisfy built-in func signature.
        """
        logging.info("SIGINT received, Exiting")
        
        self.kill_child_processes()
        self.redis_conn.close()
        sys.exit(0)


def run_derivative(brand_obj, 
                   deriv_info,
                   session_path, 
                   rdb_filename
                   ):
    """
    Runs an arbitrary derivative as a new process.

    Parameters
    ----------
    launch_obj : Supervisor or Booter class
        The class that will launch the derivative
    deriv_name : str
        The name of the derivative
    deriv_path : str
        The path to the derivative

    Raises
    ------
    DerivativeError
        If the derivative cannot be found or returns an error code
    """

    deriv_name = deriv_info['nickname']
    if 'full_path' in deriv_info:
        deriv_path = deriv_info['full_path']
    elif ('name' in deriv_info) and ('module' in deriv_info) and ('rel_path' in deriv_info):
        name = deriv_info['name']
        filename = deriv_info['filename']
        module = deriv_info['module']
        deriv_path = os.path.join(
            brand_obj.BRAND_BASE_DIR, module, "derivatives", name, filename
            )
    else:
        raise DerivativeError(
            f"Error running derivative {deriv_name}, derivative path or name and module must be defined in graph",
            deriv_name,
            brand_obj.graph_file)
    
    # validate derivative path
    if not os.path.exists(deriv_path):
        raise DerivativeError(
            f'Could not find {deriv_name} derivative at {deriv_path}',
            deriv_name,
            brand_obj.graph_file if hasattr(brand_obj, 'graph_file') else '')
    
    # This list contains the args for priority and affinity
    pre_args = []
    # Add in the args about controlling priortiy and affinity.
    if 'run_priority' in deriv_info:  # if priority is specified
        priority = deriv_info['run_priority']
        if priority:  # if priority is not None or empty
            chrt_args = ['chrt', '-f', str(int(priority))]
            pre_args = chrt_args
    if 'cpu_affinity' in deriv_info:  # if affinity is specified
        affinity = deriv_info['cpu_affinity']
        if affinity:  # if affinity is not None or empty
            taskset_args = ['taskset', '-c', str(affinity)]
            pre_args = taskset_args + pre_args
    
    # Run the derivative
    if '.py' == deriv_path[-3:]:
        p_deriv = subprocess.run(pre_args + ['python',
                                  deriv_path,
                                  rdb_filename,
                                  brand_obj.host,
                                  str(brand_obj.port),
                                  session_path],
                                  capture_output=True)
    elif '.bin' == deriv_path[-4:] or open(deriv_path,'r').readline()[:2] == "#!":
        deriv_path = "./" + deriv_path
        p_deriv = subprocess.run(pre_args + [deriv_path,
                                  rdb_filename,
                                  brand_obj.host,
                                  str(brand_obj.port),
                                  session_path],
                                  capture_output=True)
    else:
        logging.error(
            f"Derivative {deriv_name} is not Python or a Bin, nor does it "
            f"contain a shebang (#!) to let the OS know how to run it. "
            f"The derivative will not be started."
            )
        brand_obj.r.xadd(
            DERIVATIVES_STATUS_STREAM,
            {
                "nickname": deriv_name,
                "status": "completed",
                "success": 0,
                "returncode": -1,
                "stderr": -1,
                "timestamp": -1,
            },
        )
        raise DerivativeError(
            f"Derivative {deriv_name} is not Python or a Bin, nor does it " \
            f"contain a shebang (#!) to let the OS know how to run it. " \
            f"The derivative will not be started.",
            deriv_name,
            brand_obj.graph_file if hasattr(brand_obj, 'graph_file') else '')
    
    if len(p_deriv.stdout) > 0:
        brand_obj.logger.debug(p_deriv.stdout.decode())

    if p_deriv.returncode == 0:
        brand_obj.logger.info(f'{deriv_name} derivative completed')
    elif p_deriv.returncode > 0:
        raise DerivativeError(
            f'{deriv_name} derivative returned exit code {p_deriv.returncode}',
            deriv_name,
            brand_obj.graph_file if hasattr(brand_obj, 'graph_file') else '',
            p_deriv)
    elif p_deriv.returncode < 0:
        brand_obj.logger.info(f'{deriv_name} derivative was halted during execution with return code {p_deriv.returncode}, {signal.Signals(-p_deriv.returncode).name}')




