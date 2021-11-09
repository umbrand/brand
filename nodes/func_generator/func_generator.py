#!/usr/bin/env python
# -*- coding: utf-8 -*-
# func_generator.py

import gc
import logging
import os
import signal
import sys
import time

import numpy as np
from brand import get_node_parameter_value, initializeRedisFromYAML

YAML_FILE = sys.argv[1] if len(sys.argv) > 1 else 'func_generator.yaml'

# setup up logging
loglevel = get_node_parameter_value(YAML_FILE, 'func_generator', 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format='%(levelname)s:func_generator:%(message)s',
                    level=numeric_level)


class Generator():
    def __init__(self):
        self.sample_rate = get_node_parameter_value(YAML_FILE,
                                                    'func_generator',
                                                    'sample_rate')
        self.use_timer = get_node_parameter_value(YAML_FILE, 'func_generator',
                                                  'use_timer')

        # signal handlers
        signal.signal(signal.SIGINT, self.terminate)
        if self.use_timer:
            signal.signal(signal.SIGUSR1, self.send_sample)
            logging.info('Waiting for timer signal...')
        else:
            signal.signal(signal.SIGUSR1, signal.SIG_IGN)

        self.r = initializeRedisFromYAML(YAML_FILE)

        self.t: int = 0  # initialize time variable
        # set the number of features and targets
        self.n_features = get_node_parameter_value(YAML_FILE, 'func_generator',
                                                   'n_features')
        self.n_targets = get_node_parameter_value(YAML_FILE, 'func_generator',
                                                  'n_targets')
        self.duration = get_node_parameter_value(YAML_FILE, 'func_generator',
                                                 'duration')

        self.sample = {'ts': float(), 't': int()}

    def send_sample(self):
        x = np.sin(self.t_arr + (self.t * 0.05 * 2 * np.pi),
                   dtype=np.float64).dot(self.A.T)
        self.sample['ts'] = time.time()
        self.sample['t'] = self.t
        self.sample['x'] = x.tobytes()
        self.r.xadd('func_generator', self.sample)
        self.t += 1

    def build(self, n_features, n_targets):
        # set initial offsets for each target
        self.t_arr = np.arange(n_targets)
        # create array used to generate features
        self.A = np.ones((n_features, n_targets), dtype=np.float64)
        logging.info(f'Generating {n_features} features for '
                     f'{n_targets} targets')

    def run(self):
        if self.use_timer:
            while True:
                signal.pause()
        else:
            logging.info('Sending data')

            self.build(self.n_features, self.n_targets)
            last_time = 0
            start_time = time.perf_counter()
            # send samples to Redis at the specified sampling rate
            while time.perf_counter() - start_time < self.duration:
                current_time = time.perf_counter()
                if current_time - last_time >= 1 / self.sample_rate:
                    self.send_sample()
                    last_time = current_time
            logging.info('Exiting')

            # wait for the decoder to finish
            waiting = True
            while waiting:
                entry_dict = self.r.xrevrange('decoder', count=1)[0][1]
                if int(entry_dict[b't']) != self.t - 1:
                    time.sleep(1)
                else:
                    waiting = False

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


if __name__ == "__main__":
    gc.disable()

    # setup
    logging.info(f'PID: {os.getpid()}')
    gen = Generator()

    # main
    gen.run()
