#!/usr/bin/env python
# -*- coding: utf-8 -*-
# wiener_filter.py
import gc
import json
import logging
import os
import pickle
import signal
import sys
import time

import numpy as np
from brand import get_node_parameter_value, initializeRedisFromYAML
from sklearn.linear_model import Ridge

NAME = 'wiener_filter'  # name of this node
YAML_FILE = sys.argv[1] if len(sys.argv) > 1 else 'wiener_filter.yaml'
if len(sys.argv) > 2:
    N_FEATURES = int(sys.argv[2])
else:
    N_FEATURES = get_node_parameter_value(YAML_FILE, NAME, 'n_features')

# setup up logging
loglevel = get_node_parameter_value(YAML_FILE, NAME, 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format='%(levelname)s:wiener_filter:%(message)s',
                    level=numeric_level)


class Decoder():
    def __init__(self):
        # connect to Redis
        self.r = initializeRedisFromYAML(YAML_FILE)

        # build the wiener_filter
        self.n_features = N_FEATURES
        self.n_targets = get_node_parameter_value(YAML_FILE, NAME, 'n_targets')
        self.n_history = get_node_parameter_value(YAML_FILE, NAME, 'n_history')
        self.bin_size = get_node_parameter_value(YAML_FILE, NAME, 'bin_size')
        self.build()

        # initialize IDs for the two Redis streams
        self.data_id = '$'
        self.param_id = '$'

        # terminate on SIGINT
        signal.signal(signal.SIGINT, self.terminate)

    def build(self):
        self.model_path = get_node_parameter_value(YAML_FILE, NAME,
                                                   'model_path')
        try:
            with open(self.model_path, 'rb') as f:
                self.mdl = pickle.load(f)
                logging.info(f'Loaded model from {self.model_path}')
        except Exception:
            logging.warning(
                'Failed to load wiener_filter. Initializing a new one.')
            self.mdl = Ridge()
            X = np.ones((100, self.n_features * self.n_history))
            y = np.ones((100, self.n_targets))
            self.mdl.fit(X, y)

    def predict(self, x):
        # implementing this step directly instead of using mdl.predict() for
        # best performance
        y = x.dot(self.mdl.coef_.T) + self.mdl.intercept_
        return y

    def run(self):
        input_stream = b'tc_replay'
        input_dtype = 'int16'
        input_field = b'crossings'
        # initialize variables
        # entry to the decoder output stream
        decoder_entry = {
            'ts': float(),
            'ts_gen': float(),
            't': int(),
            'y': np.zeros(self.n_targets).tobytes(),
            'n_features': self.n_features,
            'n_targets': self.n_targets,
        }
        # input stream
        stream_dict = {input_stream: self.data_id}

        # count the number of entries we have read into the bin so far
        n_entries = 0
        # current window of data to use for decoding
        window = np.zeros((self.n_features, self.bin_size, self.n_history),
                          dtype=input_dtype)
        # binned decoder input
        X = np.zeros((1, self.n_features * self.n_history), dtype=input_dtype)
        # decoder output
        y = np.zeros((1, self.n_targets), dtype=np.float64)

        while True:
            while n_entries < self.bin_size:
                # read from the function generator stream
                streams = self.r.xread(stream_dict,
                                       block=0,
                                       count=self.bin_size - n_entries)
                _, stream_entries = streams[0]
                for self.data_id, entry_dict in stream_entries:
                    # load the input
                    window[:, n_entries,
                           0] = np.frombuffer(entry_dict[input_field],
                                              dtype=input_dtype)
                    n_entries += 1
                stream_dict[input_stream] = self.data_id

            X[0, :] = window.mean(axis=1).reshape(
                1, self.n_features * self.n_history)
            # generate a prediction
            y[:] = self.predict(X)
            logging.debug(y)

            # write results to Redis
            decoder_entry['ts'] = time.time()
            decoder_entry['timestamps'] = entry_dict[b'timestamps']
            decoder_entry['y'] = y.tobytes()
            self.r.xadd('decoder', decoder_entry)

            # shift window along the history axis
            window[:, :, 1:] = window[:, :, :-1]

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        gc.collect()
        sys.exit(0)


if __name__ == "__main__":
    gc.disable()

    # setup
    logging.info(f'PID: {os.getpid()}')
    dec = Decoder()
    logging.info('Waiting for data...')

    # main
    dec.run()

    gc.collect()
