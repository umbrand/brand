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

class RunDerivatives(Thread):

    def __init__(self, 
                 machine,
                 model,
                 host,
                 port,
                 brand_base_dir,
                 stop_event,
                 continue_on_error=True):
        
        super().__init__()

        self.nickname = f"derivative_runner_{machine}"

        self.step = -1
        self.machine = machine
        self.model = model

        self.redis_host = host
        self.redis_port = port
        self.redis_conn = self.connect_to_redis()

        self.brand_base_dir = brand_base_dir

        self.stop_event = stop_event

        self.run_all_if_error = continue_on_error

        self.current_thread = None
        self.thread_m1 = None

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
        for deriv, d in model['derivatives'].items():
            if 'autorun_step' in d:
                if d['autorun_step'] in steps:
                    steps[d['autorun_step']].append(d)
                else:
                    steps[d['autorun_step']] = [d]

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
            self.thread_m1 = RunDerivativeSet(
                machine=self.machine, 
                derivatives=self.steps[self.step],
                host=self.redis_host,
                port=self.redis_port,
                brand_base_dir=self.brand_base_dir,
                stop_event=self.stop_event)
            self.thread_m1.start()

        for step in self.steps:
            if step > -1:
                self.step = step
                logger.info(f"Starting derivative step {self.step}.")
                self.current_thread = RunDerivativeSet(
                    machine=self.machine, 
                    derivatives=self.steps[self.step],
                    host=self.redis_host,
                    port=self.redis_port,
                    brand_base_dir=self.brand_base_dir,
                    stop_event=self.stop_event)
                self.current_thread.start()

                # Wait for this step to finish.
                self.current_thread.join()

                # Check if thread failed on finish.
                if self.current_thread.failure_state:
                    self.errors[self.step] = True
                    logger.warning(f"Step {self.step} completed with an error(s).")
                else:
                    logger.info(f"Step {self.step} completed.")

                # If this step failed, stop running derivatives.
                if self.errors[self.step] and not self.run_all_if_error:
                    self.report_future_failure(step=self.step)
                    break

        if -1 in self.steps:
            logger.info(f"Waiting for derivative step -1 to finish.")
            self.thread_m1.join()
            
            if self.thread_m1.failure_state:
                self.errors[-1] = True
                logger.warning(f"Step -1 completed with an error(s).")
            else:
                logger.info(f"Step -1 completed.")

        logger.info(f"Derivative steps finished {f'with error(s): {self.errors}' if any(self.errors.values()) else 'successfully'}")

    def report_future_failure(self, step=-1):
        """Report the failure to start for all derivatives in future steps."""
        end_timestamp = time.time()

        failure_steps = [s for s in self.steps if s > step]
        failure_steps_derivatives = []

        for s in failure_steps:
            # Only report the error for the autorun set to True derivatives 
            # on this machine.
            self.errors[s] = True
            for d in self.steps[s]:
                if d['machine'] == self.machine:
                    nickname = d['nickname']
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

        logger.warning(f"Derivative step(s) {', '.join([str(s) for s in failure_steps])} failed to start because a previous step errored.")
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


class RunDerivativeSet(Thread):

    def __init__(self, 
                 machine,
                 derivatives,
                 host,
                 port,
                 brand_base_dir,
                 stop_event) -> None:
        """Run all derivatives in a set.
        
        Parameters
        ----------
        
        machine: str
            Which Machine the process is being run on. 
        derivatives: dict
            A dictionary containing all the derivatives to run.
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

        self.nickname = 'derivative_set_runner'

        self.machine = machine
        self.derivatives = derivatives
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

        self.running_children = {}
        self.finished_children = {}

        self.failure_state = False

        self.stop_event = stop_event

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

    def start_derivative(self, deriv_info):

        nickname = deriv_info['nickname']
        filepath = deriv_info['filepath']
        
        if '.py' == filepath[-3:]:
            args = ["python", filepath]
        elif '.bin' == filepath[-4:]:
            args = ["./" + filepath]
        elif open(filepath,'r').readline()[:2] == "#!":
            args = ["./" + filepath]
        elif open(filepath,'r').readline()[:2] != "#!":
            logger.error(
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
                    "timestamp": time.time(),
                },
            )
            return None
        
        # Build the actual args to the command. 
        args += ['-n', nickname, '-i', self.redis_host, '-p', str(self.redis_port)]    
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
        # within a set (doesn't overload the CPU maybe). 
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
        logger.info(f"Starting derivative {nickname} {delay_msg}...")

        proc = subprocess.Popen(args)
        start_timestamp = time.time()

        self.redis_conn.xadd(
            DERIVATIVES_STATUS_STREAM,
            {
                "nickname": nickname,
                "status": "running",
                "timestamp": start_timestamp,
            },
        )

        return proc

    def send_derivative_exit_status(self, nickname, proc, stderr=''):
        """
        Send the exit status of a derivative to redis
        """
        if stderr is None or stderr == '':
            stdout, stderr = proc.communicate()

        returncode = proc.poll()
        end_timestamp = time.time()
        try:
            self.redis_conn.xadd(
                DERIVATIVES_STATUS_STREAM,
                {
                    "nickname": nickname,
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
            logger.info(f"Derivative {nickname} completed successfully.")
        else:
            logger.error(f"Derivative {nickname} errored with code {returncode}.\n{stderr}")
    
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
                        end_timestamp = time.time()

                        # Remove that nickname from the list. 
                        del self.running_children[nickname]

                        # Add it to the finished_children_list.
                        self.finished_children[nickname] = proc

                        if returncode != 0:
                            self.failure_state = True

                        self.send_derivative_exit_status(nickname, proc)
                        
            # Let some time pass as the derivatives run.
            time.sleep(CHECK_WAIT_TIME)

    def kill_child_processes(self):
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

        for nickname, proc in self.running_children.items():
            try:
                # check if process exists
                os.kill(proc.pid, 0)
            except OSError:
                # process doesn't exist, may have crashed
                logger.warning(f"'{nickname}' (pid: {proc.pid})"
                                " isn't running and may have crashed")
                self.running_children[nickname] = None
                self.finished_children[nickname] = proc
                self.send_derivative_exit_status(nickname, proc, "Early termination.")
            else:
                # process is running
                # send SIGINT
                kill_proc_tree(proc.pid, signal.SIGINT)
                try:
                    # check if it terminated
                    proc.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    # SIGINT failed, so send SIGKILL
                    logger.warning(f"Could not stop '{nickname}' "
                                    f"(pid: {proc.pid}) using SIGINT")
                    kill_proc_tree(proc.pid, signal.SIGKILL)
                    try:
                        # check if it terminated
                        proc.communicate(timeout=15)
                    except subprocess.TimeoutExpired:
                        # keep the process in self.running_children to report 
                        # the error later
                        pass  # delay error message until after the loop
                    else:
                        # process terminated via SIGKILL
                        logger.info(f"Killed '{nickname}' "
                                     f"(pid: {proc.pid}) using SIGKILL")
                        self.running_children[nickname] = None
                        self.finished_children[nickname] = proc
                        self.send_derivative_exit_status(nickname, proc, "Early termination.")
                else:
                    # process terminated via SIGINT
                    logger.info(f"Stopped '{nickname}' "
                                 f"(pid: {proc.pid}) using SIGINT")
                    self.running_children[nickname] = None
                    self.finished_children[nickname] = proc
                    self.send_derivative_exit_status(nickname, proc, "Early termination.")

        # remove killed processes from self.running_children
        self.running_children = {
            n: p
            for n, p in self.running_children.items() if p is not None
        }
        # raise an error if nodes are still running
        if self.running_children:
            running_nodes = [
                f'{node} ({p.pid})' for node, p in self.running_children.items()
            ]
            message = ', '.join(running_nodes)
            logger.exception('Could not kill these nodes: '
                              f'{message}')

    def start_set(self):
        for d in self.derivatives:

            # Only try to run the derivatives for this machine
            if d['machine'] == self.machine:
                    
                proc = self.start_derivative(d)
                if proc is not None:
                    self.running_children[d['nickname']] = proc

    def check_all_derivatives(self):
        """Check that all derivatives in this set have finished,
        including those on other booters."""

        set_derivatives = [d['nickname'] for d in self.derivatives]

        while set_derivatives:
            try:
                derivative_status = self.redis_conn.xread(
                    {DERIVATIVES_STATUS_STREAM: self.latest_id},
                    block=0
                )
                for entry in derivative_status[0][1]:
                    nickname = entry[1][b'nickname'].decode('utf-8')
                    if nickname in set_derivatives:
                        # if the derivative is completed, remove it from the list
                        if entry[1][b'status'] == b'completed':
                            set_derivatives.remove(nickname)
                            if entry[1][b'success'] == b'0':
                                self.failure_state = True
            except redis.exceptions.ConnectionError:
                break

    def run(self):
        # start all the derivatives
        self.start_set()

        self.wait_for_children()

        # check that all derivatives on all booters
        # are finished before exiting
        self.check_all_derivatives()

        # Close up process.
        self.redis_conn.close()

    def terminate(self, sig, frame):
        """
        Allow this node to clean up before it is killed.

        :param sig: Unused. Only there to satisfy built-in func signature.
        :param frame: Unused. Only there to satisfy built-in func signature.
        """
        logger.info("SIGINT received, Exiting")
        
        self.kill_child_processes()
        self.redis_conn.close()
        sys.exit(0)