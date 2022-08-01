#!/usr/bin/env python
# -*- coding: utf-8 -*-
# subscriber.py
import gc
import logging
import sys
import time

import numpy as np
from brand import BRANDNode


class Subscriber(BRANDNode):

    def __init__(self):

        super().__init__()
        self.in_stream = self.parameters['in_stream'].encode()
        self.write_data = self.parameters['write_data']

    def run(self):
        entry_id = '$'
        pub_streams = {self.in_stream: entry_id}
        # initialize subscriber
        sub_entry = {
            't': bytes(),  # timestamp
            'i': bytes(),  # index
        }
        if self.write_data:
            sub_entry['x'] = bytes()  # data from publisher

        while True:
            entry = self.r.xread(pub_streams, block=0, count=1)
            entry_id, entry_dict = entry[0][1][0]
            pub_streams[self.in_stream] = entry_id

            sub_entry['i'] = entry_dict[b'i']
            if self.write_data:
                sub_entry['x'] = entry_dict[b'x']
            sub_entry['t'] = np.uint64(time.monotonic_ns()).tobytes()
            self.r.xadd(self.NAME, sub_entry)

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        sys.exit(0)


if __name__ == "__main__":
    gc.disable()

    node = Subscriber()
    node.run()

    gc.collect()
