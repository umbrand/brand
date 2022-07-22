#!/usr/bin/env python
# -*- coding: utf-8 -*-
# func_generator.py

import logging
import time
import gc
import numpy as np
import json

from brand import BRANDNode


class FunctionGenerator(BRANDNode):

    def __init__(self):

        super().__init__()

        self.sample_rate = self.parameters['sample_rate']
        self.n_features = self.parameters['n_features']
        self.n_targets = self.parameters['n_targets']
        self.stop_graph_when_done = (self.parameters['stop_graph_when_done']
                                     if 'stop_graph_when_done'
                                     in self.parameters else False)
        if ('duration' in self.parameters
                and self.parameters['duration'] is not None):
            self.duration = self.parameters['duration']
        else:
            self.duration = np.inf
        self.total_samples = np.floor(self.duration * self.sample_rate)

        # initialize output stream entry data
        self.i = 0
        self.x = np.zeros((1, self.n_features), dtype=np.float64)

        self.syncDict = {'i': self.i}
        self.syncDictJson = json.dumps(self.syncDict)

        self.stream_entry = {
            'ts': time.monotonic(),
            'sync': self.syncDictJson.encode(),
            'samples': self.x.tobytes(),
            'i': self.i
        }

        logging.info('Starting function generator...')

    def build(self):
        # set initial offsets for each target
        self.t_arr = np.arange(self.n_targets)
        # create array used to generate features
        self.A = np.ones((self.n_features, self.n_targets), dtype=np.float64)
        logging.info(f'Generating {self.n_features} features for '
                     f'{self.n_targets} targets')

    def send_sample(self):
        self.x = np.sin(self.t_arr + (self.i * 0.05 * 2 * np.pi),
                        dtype=np.float64).dot(self.A.T)

        self.syncDict = {'i': self.i}
        self.syncDictJson = json.dumps(self.syncDict)

        self.stream_entry = {
            'ts': np.uint64(time.monotonic_ns()).tobytes(),
            'sync': self.syncDictJson.encode(),
            'samples': self.x.tobytes(),
            'i': np.uint64(self.i).tobytes()
        }

        self.r.xadd('func_generator', self.stream_entry)

        self.i += 1

    def run(self):

        self.build()

        logging.info('Sending data...')

        last_time = 0
        # send samples to Redis at the specified sampling rate
        while self.i < self.total_samples:
            current_time = time.perf_counter()
            if current_time - last_time >= 1 / self.sample_rate:
                self.send_sample()
                last_time = current_time

        if self.stop_graph_when_done:
            time.sleep(1)
            self.r.xadd('supervisor_ipstream', {'commands': 'stopGraph'})


if __name__ == "__main__":
    gc.disable()

    # setup
    gen = FunctionGenerator()

    # main
    gen.run()

    gc.collect()