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
from brand import get_node_parameter_value, initializeRedisFromYAML

YAML_FILE = 'udp_send.yaml'

# setup up logging
loglevel = get_node_parameter_value(YAML_FILE, 'udp_send', 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format='%(levelname)s:udp_send:%(message)s',
                    level=numeric_level)


class UDPSender():
    def __init__(self):
        # redis
        self.r = initializeRedisFromYAML(YAML_FILE)
        self.entry_id = '$'

        # signal handler
        signal.signal(signal.SIGINT, self.terminate)

        # udp
        self.udp_ip = get_node_parameter_value(YAML_FILE, 'udp_send', 'udp_ip')
        self.udp_port = get_node_parameter_value(YAML_FILE, 'udp_send',
                                                 'udp_port')
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
                    'n_features': float(entry_dict[b'n_features']),
                    'n_targets': float(entry_dict[b'n_targets']),
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
