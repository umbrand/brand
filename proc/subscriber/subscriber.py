#!/usr/bin/env python
# -*- coding: utf-8 -*-
# subscriber.py

import gc
import logging
import signal
import sys
import time

import yaml
from redis import Redis

gc.disable()

YAML_FILE = 'subscriber.yaml'

logging.basicConfig(format='%(levelname)s:subscriber:%(message)s',
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


signal.signal(signal.SIGINT, signal_handler)

redis_socket = get_parameter_value(YAML_FILE, 'redis_socket')
if redis_socket:
    logging.info(f'Redis Socket Path {redis_socket}')
    r = Redis(unix_socket_path=redis_socket)
else:
    redis_ip = get_parameter_value(YAML_FILE, 'redis_ip')
    redis_port = get_parameter_value(YAML_FILE, 'redis_port')
    r = Redis(host=redis_ip, port=redis_port)

entry_id = '$'
xread_dict = {b'publisher': entry_id}
xadd_dict = {
    'ts': float(),
    'ts_sent': float(),
    'size': int(),
    'counter': int(),
}
while True:
    entry = r.xread(xread_dict, block=0, count=1)
    entry_id, entry_dict = entry[0][1][0]
    xread_dict[b'publisher'] = entry_id

    xadd_dict['ts'] = time.perf_counter()
    xadd_dict['ts_sent'] = float(entry_dict[b'ts'])
    xadd_dict['size'] = int(entry_dict[b'size'])
    xadd_dict['counter'] = int(entry_dict[b'counter'])
    r.xadd('subscriber', xadd_dict)
