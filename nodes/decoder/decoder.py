#!/usr/bin/env python
# -*- coding: utf-8 -*-
# decoder.py

import logging
import os
import signal
import sys
import time

import numpy as np
from brand import get_node_parameter_value, initializeRedisFromYAML
from tensorflow import keras
from tensorflow.keras import layers

YAML_FILE = sys.argv[1] if len(sys.argv) > 1 else 'decoder.yaml'

# setup up logging
loglevel = get_node_parameter_value(YAML_FILE, 'decoder', 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format='%(levelname)s:decoder:%(message)s',
                    level=numeric_level)


class Decoder():
    def __init__(self):
        # connect to Redis
        self.r = initializeRedisFromYAML('decoder.yaml')

        # build the decoder
        self.n_features = get_node_parameter_value(YAML_FILE, 'decoder',
                                                   'n_features')
        self.n_targets = get_node_parameter_value(YAML_FILE, 'decoder',
                                                  'n_targets')
        self.build()

        # initialize IDs for the two Redis streams
        self.data_id = '$'
        self.param_id = '0'

        # terminate on SIGINT
        signal.signal(signal.SIGINT, self.terminate)

    def build(self):
        self.A = np.ones([self.n_features, self.n_targets], dtype=np.float64)

    def decode(self, x):
        y = self.A.T.dot(x)
        logging.debug(y)
        return y

    def run(self):
        while True:
            stream_dict = {
                b'func_generator': self.data_id,
                b'decoder_params': self.param_id
            }
            streams = self.r.xread(stream_dict, block=0, count=1)
            logging.debug('Received data')
            stream_name, stream_entries = streams[0]
            if stream_name == b'decoder_params':
                self.param_id, entry_dict = stream_entries[0]
                self.n_features = int(entry_dict[b'n_features'])
                self.n_targets = int(entry_dict[b'n_targets'])
                logging.info('Updating decoder params: '
                             f'n_features={self.n_features}, '
                             f'n_targets={self.n_targets}')
                self.build()
                self.data_id = '$'  # skip to the latest entry in the stream
            elif stream_name == b'func_generator':
                self.data_id, entry_dict = stream_entries[0]
                x = np.frombuffer(entry_dict[b'x'], dtype=np.float64)
                ts_gen = float(entry_dict[b'ts'])
                try:
                    y = self.decode(x)
                    self.r.xadd(
                        'decoder', {
                            'ts': time.time(),
                            'ts_gen': ts_gen,
                            'y': y.tobytes(),
                            'n_features': self.n_features,
                            'n_targets': self.n_targets,
                        })
                except ValueError as exc:
                    logging.warn(repr(exc))

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


class RNNDecoder(Decoder):
    def build(self):
        self.seq_len = 1
        self.model = keras.Sequential()
        self.model.add(
            layers.Input(shape=(self.seq_len, self.n_features), batch_size=1))
        self.model.add(
            layers.SimpleRNN(self.n_features,
                             return_sequences=False,
                             stateful=True,
                             unroll=True))
        self.model.add(layers.Dense(self.n_targets))
        self.model(np.random.rand(1, self.seq_len, self.n_features))  # init

    def decode(self, x):
        y = self.model(x[None, None, :]).numpy()[0, :]
        logging.debug(y)
        return y


if __name__ == "__main__":
    decoder_type = get_node_parameter_value(YAML_FILE, 'decoder',
                                            'decoder_type')

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
