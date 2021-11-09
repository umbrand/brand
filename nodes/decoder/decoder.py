#!/usr/bin/env python
# -*- coding: utf-8 -*-
# decoder.py
import gc
import json
import logging
import os
import signal
import sys
import time

import numpy as np
from brand import get_node_parameter_value, initializeRedisFromYAML
from sklearn.linear_model import Ridge
from tensorflow import keras
from tensorflow.keras import layers

NAME = 'decoder'  # name of this node
YAML_FILE = sys.argv[1] if len(sys.argv) > 1 else 'decoder.yaml'
if len(sys.argv) > 2:
    N_FEATURES = int(sys.argv[2])
else:
    N_FEATURES = get_node_parameter_value(YAML_FILE, NAME, 'n_features')

# setup up logging
loglevel = get_node_parameter_value(YAML_FILE, NAME, 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format='%(levelname)s:decoder:%(message)s',
                    level=numeric_level)


def load_model(estimator, filepath):
    """
    Load a JSON representation of a scikit-learn model from the provided
    filepath

    Parameters
    ----------
    estimator : estimator object
        Instance of an sklearn estimator. e.g. Ridge()
    filepath : str
        path to the saved model

    Returns
    -------
    estimator : estimator object
        sklearn estimator with weights and parameters loaded from the
        filepath
    """
    with open(filepath, 'r') as f:
        model_info = json.load(f)
    estimator.set_params(**model_info['params'])
    for attr, val in model_info['attr'].items():
        if type(val) is list:
            val = np.array(val)
        setattr(estimator, attr, val)
    return estimator


class Decoder():
    def __init__(self):
        # connect to Redis
        self.r = initializeRedisFromYAML(YAML_FILE)

        # build the decoder
        self.n_features = N_FEATURES
        self.n_targets = get_node_parameter_value(YAML_FILE, NAME, 'n_targets')
        self.build()

        # initialize IDs for the two Redis streams
        self.data_id = '$'
        self.param_id = '$'

        # terminate on SIGINT
        signal.signal(signal.SIGINT, self.terminate)

    def build(self):
        self.model_path = get_node_parameter_value(YAML_FILE, NAME,
                                                   'model_path')
        self.mdl = Ridge()
        try:
            self.mdl = load_model(self.mdl, self.model_path)
        except Exception:
            logging.warning('Failed to load decoder. Initializing a new one.')
            self.mdl.fit(np.ones((100, self.n_features)),
                         np.ones((100, self.n_targets)))

    def predict(self, x):
        # implementing this step directly instead of using mdl.predict() for
        # best performance
        y = x.dot(self.mdl.coef_.T) + self.mdl.intercept_
        return y

    def run(self):
        # initialize decoder dict
        decoder_entry = {
            'ts': float(),
            'ts_gen': float(),
            't': int(),
            'y': np.zeros(self.n_targets).tobytes(),
            'n_features': self.n_features,
            'n_targets': self.n_targets,
        }
        stream_dict = {b'func_generator': self.data_id}
        while True:
            # read from the function generator stream
            streams = self.r.xread(stream_dict, block=0, count=1)
            stream_name, stream_entries = streams[0]
            self.data_id, entry_dict = stream_entries[0]
            stream_dict[b'func_generator'] = self.data_id

            # load the input and generate a prediction
            x = np.frombuffer(entry_dict[b'x'], dtype=np.float64)
            y = self.predict(x)

            # write results to Redis
            decoder_entry['ts'] = time.time()
            decoder_entry['ts_gen'] = float(entry_dict[b'ts'])
            decoder_entry['t'] = int(entry_dict[b't'])
            decoder_entry['y'] = y.tobytes()
            self.r.xadd('decoder', decoder_entry)

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

    def predict(self, x):
        y = self.model(x[None, None, :]).numpy()[0, :]
        logging.debug(y)
        return y


if __name__ == "__main__":
    gc.disable()
    gc.set_debug(gc.DEBUG_UNCOLLECTABLE)

    decoder_type = get_node_parameter_value(YAML_FILE, NAME, 'decoder_type')

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

    gc.collect()
