#!/usr/bin/env python
# -*- coding: utf-8 -*-
# udp_send.py

import gc
import json
import logging
import os
import signal
import socket
import sys
import time

import numpy as np
from brand import get_node_parameter_value, initializeRedisFromYAML

YAML_FILE = sys.argv[1] if len(sys.argv) > 1 else 'udp_send.yaml'

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
        xread_streams = {b'decoder': self.entry_id}
        sample = {
            'ts': float(),  # time sent
            'ts_dec': float(),  # time decoded
            'ts_gen': float(),  # time generated
            'n_features': float(),
            'n_targets': float()
        }
        while True:
            #  read from stream
            reply = self.r.xread(xread_streams, block=0, count=1)
            entry_list = reply[0][1]
            self.entry_id, entry_dict = entry_list[0]
            xread_streams[b'decoder'] = self.entry_id

            # send message via UDP
            message = json.dumps(np.frombuffer(entry_dict[b'y']).tolist())
            self.sock.sendto(message.encode(), (self.udp_ip, self.udp_port))

            # log timestamps to Redis
            sample['ts'] = time.time()  # time sent
            sample['ts_dec'] = float(entry_dict[b'ts'])  # time decoded
            sample['ts_gen'] = float(entry_dict[b'ts_gen'])  # time generated
            sample['n_features'] = float(entry_dict[b'n_features'])
            sample['n_targets'] = float(entry_dict[b'n_targets'])
            self.r.xadd('udp_send', sample)

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


if __name__ == "__main__":
    gc.disable()
    # setup
    logging.info(f'PID: {os.getpid()}')
    dec = UDPSender()
    logging.info('Waiting for data...')

    # main
    dec.run()
