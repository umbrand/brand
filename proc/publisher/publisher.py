#!/usr/bin/env python
# -*- coding: utf-8 -*-
# publisher.py

import gc
import logging
import signal
import sys
import time

import numpy as np
import yaml
from redis import Redis

gc.disable()

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
    redis_socket = get_parameter_value(YAML_FILE, 'redis_socket')
    if redis_socket:
        logging.info(f'Redis Socket Path {redis_socket}')
        r = Redis(unix_socket_path=redis_socket)
    else:
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
    # dynamic_sizes = 30 * 128 * np.arange(1, n_arrays + 1)
    dynamic_sizes = np.logspace(3, 23, base=2, num=21, dtype=np.uint64)
else:
    dynamic_sizes = [30 * 128 * 2]

DURATION = get_parameter_value(YAML_FILE, 'duration')  # seconds
SAMPLE_RATE = get_parameter_value(YAML_FILE, 'sample_rate')  # Hz
DTYPE = get_parameter_value(YAML_FILE, 'data_type')
MAXLEN = get_parameter_value(YAML_FILE, 'maxlen')

try:
    data_type = np.dtype(DTYPE)
except TypeError:
    logging.error(f'The data_type {DTYPE} was not understood. Please specify '
                  'the data type in a format compatible with numpy.dtype().'
                  'Exiting.')
    sys.exit(0)

# main loop
for dynamic_size in dynamic_sizes:
    n_items: int = int(dynamic_size) // np.dtype(data_type).itemsize
    counter: int = 0
    last_time: float = 0
    logging.info(f'Sending {dynamic_size} byte {DTYPE} arrays for '
                 f'{DURATION} seconds. MAXLEN = {MAXLEN}.')
    stream_dict = {
        'ts': float(),
        'val': np.ones(n_items, dtype=data_type).tobytes(),
        'size': int(dynamic_size),
        'counter': counter,
    }
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < DURATION:
        current_time: float = time.perf_counter()
        if current_time - last_time >= 1 / SAMPLE_RATE:
            stream_dict['ts'] = current_time
            stream_dict['counter'] = counter
            r.xadd(name='publisher',
                   fields=stream_dict,
                   maxlen=MAXLEN)
            counter += 1
            last_time = current_time

    # wait for the subscriber to finish
    waiting = True
    while waiting:
        entry_dict = r.xrevrange('subscriber', count=1)[0][1]
        if int(entry_dict[b'counter']) != counter - 1:
            time.sleep(1)
        else:
            waiting = False

    gc.collect()
