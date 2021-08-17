#!/usr/bin/env python
# -*- coding: utf-8 -*-
# publisher.py

import logging
import signal
import sys
import time

import numpy as np
import yaml
from redis import Redis

YAML_FILE = 'publisher.yaml'

logging.basicConfig(format='%(levelname)s:publisher:%(message)s',
                    level=logging.INFO)


def get_parameter_value(fileName, field):
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


# setting up clean exit code
def signal_handler(sig, frame):  # setup the clean exit code with a warning
    logging.info('SIGINT received, Exiting')
    sys.exit(0)


# place the sigint signal handler
signal.signal(signal.SIGINT, signal_handler)

# connect to redis, figure out the streams of interest
try:
    redis_ip = get_parameter_value(YAML_FILE, 'redis_ip')
    redis_port = get_parameter_value(YAML_FILE, 'redis_port')
    logging.info(f'Redis IP {redis_ip};  Redis port: {redis_port}')
    r = Redis(host=redis_ip, port=redis_port)
    logging.info('Connecting to Redis...')
except Exception:
    logging.info('Failed to connect to Redis. Exiting.')
    sys.exit()

n_arrays = 6
if get_parameter_value(YAML_FILE, 'many_dynamic_sizes'):
    dynamic_sizes = 30 * 128 * np.arange(1, n_arrays + 1)
else:
    dynamic_sizes = [8]

DURATION = get_parameter_value(YAML_FILE, 'duration')  # seconds
SAMPLE_RATE = get_parameter_value(YAML_FILE, 'sample_rate')  # Hz
DTYPE = get_parameter_value(YAML_FILE, 'data_type')

try:
    data_type = np.dtype(DTYPE)
except TypeError:
    logging.error(f'The data_type {DTYPE} was not understood. Please specify '
                  'the data type in a format compatible with numpy.dtype().'
                  'Exiting.')
    sys.exit(0)

# main loop
for n_items in dynamic_sizes:
    counter = np.uint64(0)
    last_time = 0
    logging.info(f'Sending {n_items}-item {DTYPE} arrays for '
                 f'{DURATION} seconds')
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < DURATION:
        current_time = time.perf_counter()
        if current_time - last_time >= 1 / SAMPLE_RATE:
            data = np.zeros(n_items, dtype=data_type)
            r.xadd(
                'publisher', {
                    'ts': current_time,
                    'val': data.tobytes(),
                    'size': int(n_items),
                    'counter': int(counter),
                })
            counter += 1
            last_time = current_time
# Encoding numpy arrays in Redis: https://stackoverflow.com/questions/55311399
