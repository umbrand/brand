#!/usr/bin/env python
# -*- coding: utf-8 -*-
# func_generator.py

import gc
import json
import logging
import time

import numpy as np
from brand import BRANDNode
from brand.timing import clock_nanosleep


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
        i = 0
        self.x = np.zeros((1, self.n_features), dtype=np.float64)

        self.syncDict = {'i': i}
        self.syncDictJson = json.dumps(self.syncDict)

        self.stream_entry = {
            'ts': time.monotonic(),
            'sync': self.syncDictJson.encode(),
            'samples': self.x.tobytes(),
            'i': i
        }

        logging.info('Starting function generator...')

    def build(self):
        # set initial offsets for each target
        self.t_arr = np.arange(self.n_targets)
        # create array used to generate features
        self.A = np.ones((self.n_features, self.n_targets), dtype=np.float64)
        logging.info(f'Generating {self.n_features} features for '
                     f'{self.n_targets} targets')

    def send_sample(self, i):
        self.x = np.sin(self.t_arr + (i * 0.05 * 2 * np.pi),
                        dtype=np.float64).dot(self.A.T)

        self.syncDict['i'] = i
        self.syncDictJson = json.dumps(self.syncDict)

        self.stream_entry['ts'] = np.uint64(time.monotonic_ns()).tobytes()
        self.stream_entry['sync'] = self.syncDictJson.encode()
        self.stream_entry['samples'] = self.x.tobytes()
        self.stream_entry['i'] = np.uint64(i).tobytes()

        self.r.xadd('func_generator', self.stream_entry)

    def run(self):

        self.build()

        logging.info('Sending data...')

        # send samples to Redis at the specified sampling rate
        interval = 1_000_000_000 // self.sample_rate  # nanoseconds
        start_time = time.monotonic_ns()
        i = 0
        while i < self.total_samples:
            self.send_sample(i)
            i += 1
            clock_nanosleep(start_time + i * interval,
                            clock=time.CLOCK_MONOTONIC)

        if self.stop_graph_when_done:
            time.sleep(1)  # give the downstream nodes some time to process
            self.r.xadd('supervisor_ipstream', {'commands': 'stopGraph'})


if __name__ == "__main__":
    gc.disable()

    # setup
    gen = FunctionGenerator()

    # main
    gen.run()

    gc.collect()
