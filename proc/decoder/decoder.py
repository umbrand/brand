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

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


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

        self.n_features = get_parameter_value(YAML_FILE, 'n_features')
        self.n_targets = get_parameter_value(YAML_FILE, 'n_targets')

        self.A = np.ones([self.n_features, self.n_targets], dtype=np.float64)

        self.entry_id = '$'

        signal.signal(signal.SIGINT, self.terminate)

    def decode(self, x):
        y = self.A.T.dot(x)
        logging.debug(y)
        return y

    def run(self):
        while True:
            entry = self.r.xread({b'func_generator': self.entry_id},
                                 block=0,
                                 count=1)
            logging.debug('Received data')
            self.entry_id, entry_dict = entry[0][1][0]
            x = np.frombuffer(entry_dict[b'x'], dtype=np.float64)
            y = self.decode(x)
            self.r.xadd(
                'decoder', {
                    'ts': time.time(),
                    'ts_gen': float(entry_dict[b'ts']),
                    'y': y.tobytes(),
                })

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


class RNNDecoder(Decoder):
    def __init__(self):
        super().__init__()
        self.seq_len = 1

        self.model = keras.Sequential()
        self.model.add(layers.Input(shape=(self.seq_len, self.n_features)))
        self.model.add(
            layers.SimpleRNN(self.n_features, return_sequences=False))
        self.model.add(layers.Dense(self.n_targets))
        self.model(np.random.rand(1, self.seq_len, self.n_features))  # compile

    def decode(self, x):
        y = self.model(x[None, None, :]).numpy()[0, :]
        logging.debug(y)
        return y


if __name__ == "__main__":
    decoder_type = get_parameter_value(YAML_FILE, 'decoder_type')

    # setup
    logging.info(f'PID: {os.getpid()}')
    logging.info(f'Decoder type: {decoder_type}')
    if decoder_type.lower() == 'rnn':
        dec = RNNDecoder()
    else:
        dec = Decoder()
    logging.info('Waiting for data...')

    # main
    dec.run()
