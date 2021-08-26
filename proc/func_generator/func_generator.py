#!/usr/bin/env python
# -*- coding: utf-8 -*-
# func_generator.py

import logging
import os
import signal
import sys
import time

import numpy as np
import yaml
from redis import Redis

YAML_FILE = 'func_generator.yaml'


def get_parameter_value(fileName, field):
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


# setup up logging
loglevel = get_parameter_value(YAML_FILE, 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format='%(levelname)s:func_generator:%(message)s',
                    level=numeric_level)


class Generator():
    def __init__(self):
        self.sample_rate = get_parameter_value(YAML_FILE, 'sample_rate')
        self.use_timer = get_parameter_value(YAML_FILE, 'use_timer')

        # signal handlers
        signal.signal(signal.SIGINT, self.terminate)
        if self.use_timer:
            signal.signal(signal.SIGUSR1, self.send_sample)
            logging.info('Waiting for timer signal...')
        else:
            signal.signal(signal.SIGUSR1, signal.SIG_IGN)

        self.t = 0

        redis_ip = get_parameter_value(YAML_FILE, 'redis_ip')
        redis_port = get_parameter_value(YAML_FILE, 'redis_port')
        logging.info(f'Redis IP {redis_ip};  Redis port: {redis_port}')
        self.r = Redis(host=redis_ip, port=redis_port)
        logging.info('Connecting to Redis...')

        self.n_features = get_parameter_value(YAML_FILE, 'n_features')
        self.n_targets = get_parameter_value(YAML_FILE, 'n_targets')

        self.build()

    def send_sample(self, *args, **kwargs):
        x = np.sin(self.t_arr + (self.t * 0.05 * 2 * np.pi),
                   dtype=np.float64).dot(self.A.T)
        self.r.xadd('func_generator', {
            'ts': time.time(),
            't': self.t,
            'x': x.tobytes(),
        })
        self.t += 1

    def build(self):
        # set initial offsets for each target
        self.t_arr = np.arange(self.n_targets)
        # create array used to generate features
        self.A = np.ones([self.n_features, self.n_targets], dtype=np.float64)
        self.r.xadd(
            'decoder_params', {
                'ts': time.time(),
                'n_features': int(self.n_features),
                'n_targets': int(self.n_targets),
            })

    def run(self):
        if self.use_timer:
            while True:
                signal.pause()
        else:
            logging.info('Sending data')
            for self.n_features in 64 * np.arange(1, 6):
                logging.info('Updating function generator: '
                             f'n_features={self.n_features}, '
                             f'n_targets={self.n_targets}')
                self.build()
                last_time = 0
                start_time = time.perf_counter()
                while time.perf_counter() - start_time < 30:
                    current_time = time.perf_counter()
                    if current_time - last_time >= 1 / self.sample_rate:
                        self.send_sample()
                        last_time = current_time
            logging.info('Exiting')

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


if __name__ == "__main__":
    # setup
    logging.info(f'PID: {os.getpid()}')
    gen = Generator()

    # main
    gen.run()
