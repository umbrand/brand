#!/usr/bin/env python
# -*- coding: utf-8 -*-
# publisher.py
import gc
import logging
import sys
import time

import numpy as np
from brand import BRANDNode


class Publisher(BRANDNode):

    def __init__(self):

        super().__init__()

        # get parameters
        self.n_channels = self.parameters['n_channels']
        self.seq_len = self.parameters['seq_len']
        self.data_type = self.parameters['data_type']
        self.duration = self.parameters['duration']
        self.sample_rate = self.parameters['sample_rate']

        self.data = np.random.randn(self.n_channels,
                                    self.seq_len).astype(
                                        self.data_type)

        self.total_samples = int(self.duration * self.sample_rate)

        # initialize IDs for the two Redis streams
        self.data_id = '$'

    def run(self):
        # calculate the time between samples
        sample_period_ns = int((1 / self.sample_rate) * 1e9)
        # initialize publisher dict
        publisher_entry = {
            't': float(),  # timestamp
            'i': int(),  # index
            'x': self.data.tobytes(),
        }
        last_time = 0
        i = 0
        while i < self.total_samples:
            current_time = time.monotonic_ns()
            if current_time - last_time >= sample_period_ns:
                # write results to Redis
                publisher_entry['i'] = np.uint64(i).tobytes()
                publisher_entry['t'] = np.uint64(
                    time.monotonic_ns()).tobytes()
                self.r.xadd('publisher', publisher_entry)
                # update index and timestamp
                i += 1
                last_time = current_time

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


if __name__ == "__main__":
    gc.disable()

    node = Publisher()
    node.run()

    gc.collect()
