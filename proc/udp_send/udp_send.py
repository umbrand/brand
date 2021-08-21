#!/usr/bin/env python
# -*- coding: utf-8 -*-
# udp_send.py

import json
import logging
import os
import signal
import socket
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


YAML_FILE = 'udp_send.yaml'

# setup up logging
loglevel = get_parameter_value(YAML_FILE, 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format='%(levelname)s:udp_send:%(message)s',
                    level=numeric_level)


class UDPSender():
    def __init__(self):
        # redis
        redis_ip = get_parameter_value(YAML_FILE, 'redis_ip')
        redis_port = get_parameter_value(YAML_FILE, 'redis_port')
        logging.info(f'Redis IP {redis_ip};  Redis port: {redis_port}')
        self.r = Redis(host=redis_ip, port=redis_port)
        logging.info('Connecting to Redis...')

        self.entry_id = '$'

        # signal handler
        signal.signal(signal.SIGINT, self.terminate)

        # udp
        self.udp_ip = get_parameter_value(YAML_FILE, 'udp_ip')
        self.udp_port = get_parameter_value(YAML_FILE, 'udp_port')
        self.sock = socket.socket(
            socket.AF_INET,  # Internet
            socket.SOCK_DGRAM)  # UDP

    def run(self):
        while True:
            #  read from stream
            reply = self.r.xread({b'decoder': self.entry_id}, block=0, count=1)
            entry_list = reply[0][1]
            self.entry_id, entry_dict = entry_list[0]
            logging.debug('Received data')

            # send message
            message = json.dumps(np.frombuffer(entry_dict[b'y']).tolist())
            self.sock.sendto(message.encode(), (self.udp_ip, self.udp_port))

            # log to Redis
            self.r.xadd(
                'udp_send',
                {
                    'ts': time.time(),  # time sent
                    'ts_dec': float(entry_dict[b'ts']),  # time decoded
                    'ts_gen': float(entry_dict[b'ts_gen']),  # time generated
                })

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


if __name__ == "__main__":
    # setup
    logging.info(f'PID: {os.getpid()}')
    dec = UDPSender()
    logging.info('Waiting for data...')

    # main
    dec.run()
