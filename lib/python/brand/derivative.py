# BRAND derivative template
# Author: Brandon Jacques, Sam Nason-Tomaszewski
# Adapted from code by: David Brandman and Kushant Patel

import coloredlogs
import logging
import os
import psutil
import redis
import signal
import subprocess
import sys
import time

from redis import Redis

from threading import Thread

from .redis import RedisLoggingHandler

# EXAMPLE DERIVATIVE YAML CONFIGS, BOTH WORK. 

#   - nickname:     this_derivative
#     name:         derivative_one.py
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

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG', logger=logger)

class AutorunDerivatives(Thread):

    def __init__(self, 
                 model,
                 host,
                 port,
                 stop_event,
                 continue_on_error=True):
        
        super().__init__()

        self.nickname = f"autorun_derivatives"

        self.step = -1
        self.model = model

        self.redis_host = host
        self.redis_port = port
        self.redis_conn = self.connect_to_redis()

        # get latest Redis ID in DERIVATIVES_STATUS_STREAM
        latest_entry = self.redis_conn.xrevrange(DERIVATIVES_STATUS_STREAM, '+', '-', count=1)
        if len(latest_entry) > 0:
            self.latest_id = latest_entry[0][0]
        else:
            self.latest_id = 0

        self.stop_event = stop_event

        self.run_all_if_error = continue_on_error

        # A dictionary with the steps as keys and a list of derivatives as values
        self.steps = {}
        # A list of derivatives that are currently running
        self.running_derivatives = []

        # Also send logs to Redis, only add handler if not present yet
        if not any(isinstance(h, RedisLoggingHandler) for h in logger.handlers):
            self.redis_log_handler = RedisLoggingHandler(
                self.redis_conn, self.nickname
            )
            logger.addHandler(self.redis_log_handler)

    def get_steps(self, model=None):
        """Gets the derivative steps from the supergraph. 
        Paramters
        ---------
        model: dict
            A dictionary containing the current supergraph."""
        
        if model is None:
            model = self.model

        steps = {}
        for derivative_nickname, derivative_info in model['derivatives'].items():
            if 'autorun_step' in derivative_info:
                if derivative_info['autorun_step'] in steps:
                    steps[derivative_info['autorun_step']].append(derivative_nickname)
                else:
                    steps[derivative_info['autorun_step']] = [derivative_nickname]

        steps = {k: steps[k] for k in sorted(steps)}
        self.steps = steps
        self.errors = {step: False for step in self.steps}

    def run(self):
        """Runs the thread. Gets steps, creates a new thread for each step."""
        # Sets self.steps and sorts it.
        self.get_steps()

        if -1 in self.steps:
            self.step = -1
            logger.info(f"Starting derivative step {self.step}.")
            self.redis_conn.xadd(
                'supervisor_ipstream',
                {'commands': 'runDerivatives',
                 'derivatives': ','.join(self.steps[self.step])})
            self.running_derivatives.extend(self.steps[self.step])

        for step in self.steps:
            if step > -1:
                self.step = step
                logger.info(f"Starting derivative step {self.step}.")
                self.redis_conn.xadd(
                    'supervisor_ipstream',
                    {'commands': 'runDerivatives',
                     'derivatives': ','.join(self.steps[self.step])})
                
                self.running_derivatives.extend(self.steps[self.step])

                self.wait_for_derivatives(step)

                if (self.stop_event.is_set()
                    or (self.errors[step]
                        and not self.run_all_if_error)):
                    self.report_future_failure(self.step)
                    break

        if -1 in self.steps:
            logger.info(f"Waiting for derivative step -1 to finish.")
            self.wait_for_derivatives(-1)

        logger.info(f"Derivative steps finished {f'with error(s): {self.errors}' if any(self.errors.values()) else 'successfully'}")

    def wait_for_derivatives(self, step):
        """Waits for derivatives in a step to finish."""
        step_derivatives = list(set(self.steps[step]).intersection(self.running_derivatives))
        while step_derivatives:
            try:
                # get latest derivative statuses
                derivative_status = self.redis_conn.xread(
                    {DERIVATIVES_STATUS_STREAM: self.latest_id},
                    block=int(CHECK_WAIT_TIME*1000))
                if derivative_status:
                    for entry in derivative_status[0][1]:
                        nickname = entry[1][b'nickname'].decode('utf-8')
                        if nickname in self.running_derivatives:
                            # if the derivative is completed, remove it from the list
                            if entry[1][b'status'] == b'completed':
                                if nickname in step_derivatives:
                                    step_derivatives.remove(nickname)
                                self.running_derivatives.remove(nickname)
                                if entry[1][b'success'] == b'0':
                                    self.errors[step] = True
                    self.latest_id = derivative_status[0][1][-1][0].decode('utf-8')

                if self.stop_event.is_set():
                    self.errors[step] = True
                    break

            except redis.exceptions.ConnectionError:
                break
        
        if self.errors[step]:
            logger.warning(f"Step {step} completed with an error(s).")
        else:
            logger.info(f"Step {step} completed.")

    def report_future_failure(self, step=-1):
        """Report the failure to start for all derivatives in future steps."""

        end_timestamp = time.time()

        failure_steps_derivatives = []
        failure_steps = [s for s in self.steps if s > step]

        # kill derivatives currently running
        self.redis_conn.xadd(
            'supervisor_ipstream',
            {'commands': 'killDerivatives',
             'derivatives': ','.join(self.running_derivatives)})

        for s in failure_steps:
            # Report failure for all derivatives in future steps
            self.errors[s] = True
            for nickname in self.steps[s]:
                failure_steps_derivatives.append(nickname)
                try:
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
                except redis.exceptions.ConnectionError:
                    pass

        logger.warning(f"Derivative step(s) {', '.join([str(s) for s in failure_steps])} failed because a previous step errored.")
        logger.warning(f"Derivative(s) {', '.join(failure_steps_derivatives)} did not run.")

    def connect_to_redis(self):
        """
        Connect to redis, and add an initial entry to indicate this node successfully
        initialized.

        :return redis.Redis:
        """

        # Attempt to connect to redis.
        try:
            redis_conn = Redis(self.redis_host, self.redis_port, retry_on_timeout=True)
        except ConnectionError as e:
            print(f"[{self.nickname}] unable to connect to redis. Error: {e}")
            sys.exit(1)

        return redis_conn

class RunDerivative(Thread):
    def __init__(self,
                 derivative_info,
                 host,
                 port,
                 stop_event) -> None:
        """Run a single derivative.
        
        Parameters
        ----------
        
        machine: str
            Which Machine the process is being run on. 
        nickname: str
            The nickname of the derivative.
        filepath: str
            The path to the derivative.
        host: str
            Redis IP address
        port: int
            Redis port number
        brand_base_dir: str
            The BRAND base directory
        stop_event: threading.Event
            An event to stop the thread.
        """
        
        super().__init__()

        self.derivative_info = derivative_info
        self.nickname = self.derivative_info['nickname']
        self.filepath = self.derivative_info['filepath']

        self.redis_host = host
        self.redis_port = port 
        # Connect to redis.
        self.redis_conn = self.connect_to_redis()

        self.stop_event = stop_event

        # get latest Redis ID in DERIVATIVES_STATUS_STREAM
        latest_entry = self.redis_conn.xrevrange(DERIVATIVES_STATUS_STREAM, '+', '-', count=1)
        if len(latest_entry) > 0:
            self.latest_id = latest_entry[0][0]
        else:
            self.latest_id = 0

        self.child = None

        self.failure_state = False

    def connect_to_redis(self):
        """
        Connect to redis, and add an initial entry to indicate this node successfully
        initialized.

        :return redis.Redis:
        """

        # Attempt to connect to redis.
        try:
            redis_conn = Redis(self.redis_host, self.redis_port, retry_on_timeout=True)
        except ConnectionError as e:
            print(f"[{self.nickname}] unable to connect to redis. Error: {e}")
            sys.exit(1)

        return redis_conn

    def start_derivative(self):
        
        if '.py' == self.filepath[-3:]:
            args = ["python", self.filepath]
        elif '.bin' == self.filepath[-4:]:
            args = ["./" + self.filepath]
        elif open(self.filepath,'r').readline()[:2] == "#!":
            args = ["./" + self.filepath]
        elif open(self.filepath,'r').readline()[:2] != "#!":
            logger.error(
                f"Derivative {self.nickname} is not Python or a Bin, nor does it "
                f"contain a shebang (#!) to let the OS know how to run it. "
                f"The derivative will not be started."
                )
            self.redis_conn.xadd(
                DERIVATIVES_STATUS_STREAM,
                {
                    "nickname": self.nickname,
                    "status": "completed",
                    "success": 0,
                    "returncode": -1,
                    "stderr": -1,
                    "timestamp": time.time(),
                },
            )
            return None
        
        # Build the actual args to the command. 
        args += ['-n', self.nickname, '-i', self.redis_host, '-p', str(self.redis_port)]    
        # Add in the args about controlling priortiy and affinity.
        if 'run_priority' in self.derivative_info:  # if priority is specified
            priority = self.derivative_info['run_priority']
            if priority:  # if priority is not None or empty
                chrt_args = ['chrt', '-f', str(int(priority))]
                args = chrt_args + args
        if 'cpu_affinity' in self.derivative_info:  # if affinity is specified
            affinity = self.derivative_info['cpu_affinity']
            if affinity:  # if affinity is not None or empty
                taskset_args = ['taskset', '-c', str(affinity)]
                args = taskset_args + args
        # You can specify a derivative to start after some short delay even 
        # within a set (doesn't overload the CPU maybe). 
        if 'delay_sec' in self.derivative_info:
            delay_sec = self.derivative_info['delay_sec']
            delay_args = ['sleep', delay_sec, "&&"]
        else:
            delay_sec = None
            delay_args = []
        args = delay_args + args

        delay_msg = (
            f"in {delay_sec} seconds " if delay_sec is not None else ""
        )
        logger.info(f"Starting derivative {self.nickname} {delay_msg}...")

        proc = subprocess.Popen(args)
        start_timestamp = time.time()

        self.redis_conn.xadd(
            DERIVATIVES_STATUS_STREAM,
            {
                "nickname": self.nickname,
                "status": "running",
                "timestamp": start_timestamp,
            },
        )

        self.child = proc

    def _kill_proc_tree(self, sig=signal.SIGTERM, include_parent=True):
        """
        Kill a process tree (including grandchildren) with signal "sig"
        """
        parent = psutil.Process(self.child.pid)
        children = parent.children(recursive=False)
        if include_parent:
            children.append(parent)
        for p in children:
            try:
                p.send_signal(sig)
            except psutil.NoSuchProcess:
                pass

    def kill_child_processes(self):
        '''
        Kills child processes
        '''

        try:
            # check if process exists
            os.kill(self.child.pid, 0)
        except OSError:
            # process doesn't exist, may have crashed
            logger.warning(f"'{self.nickname}' (pid: {self.child.pid})"
                            " isn't running and may have crashed")
            self.send_derivative_exit_status(self.nickname, self.child, "Early termination.")
            self.child = None
        else:
            # process is running
            # send SIGINT
            self._kill_proc_tree(signal.SIGINT)
            try:
                # check if it terminated
                self.child.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                # SIGINT failed, so send SIGKILL
                logger.warning(f"Could not stop '{self.nickname}' "
                               f"(pid: {self.child.pid}) using SIGINT")
                self._kill_proc_tree(signal.SIGKILL)
                try:
                    # check if it terminated
                    self.child.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    # keep the process in self.running_children to report 
                    # the error later
                    pass  # delay error message until after the loop
                else:
                    # process terminated via SIGKILL
                    logger.info(f"Killed '{self.nickname}' "
                                f"(pid: {self.child.pid}) using SIGKILL")
                    self.send_derivative_exit_status("Early termination.")
                    self.child = None
            else:
                # process terminated via SIGINT
                logger.info(f"Stopped '{self.nickname}' "
                            f"(pid: {self.child.pid}) using SIGINT")
                self.send_derivative_exit_status("Early termination.")
                self.child = None

        # raise an error if nodes are still running
        if self.child is not None:
            logger.exception(f'Could not kill {self.nickname}')

    def send_derivative_exit_status(self, stderr=''):
        """
        Send the exit status of a derivative to redis
        """
        if stderr is None or stderr == '':
            stdout, stderr = self.child.communicate()

        returncode = self.child.poll()
        end_timestamp = time.time()
        try:
            self.redis_conn.xadd(
                DERIVATIVES_STATUS_STREAM,
                {
                    "nickname": self.nickname,
                    "status": "completed",
                    "success": int(returncode == 0),
                    "returncode": returncode,
                    "stderr": '' if stderr is None else stderr,
                    "timestamp": end_timestamp
                }
            )
        except redis.exceptions.ConnectionError:
            pass

        if returncode == 0:
            logger.info(f"Derivative {self.nickname} completed successfully.")
        else:
            logger.error(f"Derivative {self.nickname} errored with code {returncode}.\n{stderr}")
            self.failure_state = True
    
    def wait_for_child(self):

        while True: 

            try:
                self.child.wait(timeout=CHECK_WAIT_TIME)
                self.send_derivative_exit_status()
                self.child = None
                break
            except subprocess.TimeoutExpired:
                pass

            if self.stop_event.is_set():
                self.failure_state = True
                self.kill_child_processes()
                break

    def run(self):
        # start all the derivatives
        self.start_derivative()

        self.wait_for_child()

        # Close up process.
        self.redis_conn.close()