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

if get_parameter_value(YAML_FILE, 'many_dynamic_sizes'):
    dynamic_sizes = np.logspace(3, 23, base=2, num=21, dtype=np.uint64)
else:
    dynamic_sizes = [8]

DURATION = get_parameter_value(YAML_FILE, 'duration')  # seconds
# main loop
for nbytes in dynamic_sizes:
    logging.info(f'Sending {nbytes} byte messages for {DURATION} seconds')
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < DURATION:
        data = np.zeros(nbytes, dtype=np.uint64)
        r.xadd('publisher', {
            'ts': time.perf_counter(),
            'val': data.tobytes(),
            'size': int(nbytes)
        })

# Encoding numpy arrays in Redis: https://stackoverflow.com/questions/55311399
