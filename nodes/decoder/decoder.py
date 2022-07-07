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
from brand import BRANDNode, BRANDNodeOld
from sklearn.linear_model import Ridge

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

class Decoder(BRANDNode):
    def __init__(self):
        
        super().__init__()

        # build the decoder
        self.n_features = self.parameters['n_features']
        self.n_targets = self.parameters['n_targets']
        self.model_path = self.parameters['model_path']
        
        self.build()

        # initialize IDs for the two Redis streams
        self.data_id = '$'
        self.param_id = '$'

    def build(self):
        
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
            'i': int(),
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
            x = np.frombuffer(entry_dict[b'samples'], dtype=np.float64)
            y = self.predict(x)

            # write results to Redis
            decoder_entry['ts'] = time.monotonic()
            decoder_entry['ts_gen'] = float(entry_dict[b'ts'])
            decoder_entry['i'] = int(entry_dict[b'i'])
            decoder_entry['y'] = y.tobytes()
            self.r.xadd('decoder', decoder_entry)

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


if __name__ == "__main__":
    gc.disable()
    gc.set_debug(gc.DEBUG_UNCOLLECTABLE)

    # setup
    dec = Decoder()

    # main
    dec.run()

    gc.collect()