#!/usr/bin/env python
# -*- coding: utf-8 -*-
# decoder.py

import logging
import os
import signal
import sys
import time

import numpy as np
import yaml
from redis import Redis


def get_parameter_value(fileName, field):
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


YAML_FILE = 'decoder.yaml'

# setup up logging
loglevel = get_parameter_value(YAML_FILE, 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format='%(levelname)s:decoder:%(message)s',
                    level=numeric_level)


class Decoder():
    def __init__(self):
        redis_ip = get_parameter_value(YAML_FILE, 'redis_ip')
        redis_port = get_parameter_value(YAML_FILE, 'redis_port')
        logging.info(f'Redis IP {redis_ip};  Redis port: {redis_port}')
        self.r = Redis(host=redis_ip, port=redis_port)
        logging.info('Connecting to Redis...')

        self.A = np.ones([100, 1], dtype=np.float64)

        self.entry_id = '$'

        signal.signal(signal.SIGINT, self.terminate)

    def decode(self, x):
        y = self.A.T.dot(x)
        logging.debug(y)
        return y

    def run(self):
        while True:
            entry = self.r.xread({b'func_generator': self.entry_id}, block=0)
            logging.debug('Received data')
            self.entry_id, entry_dict = entry[0][1][0]
            x = np.frombuffer(entry_dict[b'x'], dtype=np.float64)
            self.r.xadd(
                'decoder', {
                    'ts': time.time(),
                    'ts_gen': float(entry_dict[b'ts']),
                    'y': self.decode(x).tobytes()
                })

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


if __name__ == "__main__":
    # setup
    logging.debug(f'PID: {os.getpid()}')
    dec = Decoder()
    logging.info('Waiting for data...')

    # main
    dec.run()
