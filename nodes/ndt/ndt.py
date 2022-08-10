#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ndt.py

import gc
import sys
import time
import yaml
import signal
import logging
import numpy as np
from src.model import NDT
from brand import BRANDNode

import torch
torch.set_num_threads(1)

dtypes = {
    'int64':torch.int64,
    'float64':torch.float64,
}

class NDTNode(BRANDNode):
    def __init__(self):
        super().__init__()

        # set up streams
        self.in_stream = self.parameters['input_stream']
        self.in_field = self.parameters['input_field']
        self.in_dtype = self.parameters['input_dtype']

        # load the configuration file for the model
        self.cfg_path = self.parameters['cfg_path']
        self.cfg = yaml.safe_load(open(self.cfg_path, 'r'))

        # set input sizes
        self.seq_len = self.cfg['seq_len']
        self.data_dim = self.cfg['input_dim']

        # load the saved model
        self.model = NDT(self.cfg, 0.0, 1.0)
        self.model.eval()

        warmup_window = torch.zeros((1, self.seq_len, self.data_dim), dtype=torch.float32)
        with torch.no_grad():
            self.model(warmup_window)

        # initialize IDs for the two Redis streams
        self.data_id = '$'
        self.param_id = '$'

        # terminate on SIGINT
        signal.signal(signal.SIGINT, self.terminate)

    def run(self):
        input_stream = self.in_stream.encode()
        input_dtype = self.in_dtype
        input_field = self.in_field.encode()

        warmup_window = torch.zeros((1, self.seq_len, self.data_dim), dtype=torch.float32)
        with torch.no_grad():
            self.model(warmup_window)

        # initialize entry to  output stream
        ndt_entry = {
            'ts_after': float(),
            'ts_before': float(),
            'ts_read': float(),
            'ts_add': float(),
            'ts_in': float(),
            'i': int(),
            'i_in': int()
        }

        # input stream
        stream_dict = {input_stream: self.data_id}

        # current window of data to use for inference
        window = np.zeros((1, self.seq_len, self.data_dim), dtype=np.float32) 

        # NDT output
        y = torch.zeros(self.data_dim, dtype=torch.float32)
        x = torch.zeros((1, self.seq_len, self.data_dim), dtype=torch.float32)

        streams = None
        stream_entries = None

        i = 0
        i_in = 0
        ts_in = 0.0
        ts_read = 0.0
        ts_before = 0.0
        n_bins = 0  # number of bins we have read into the sequence so far

        logging.info('Ready to receive data')
        while True:
            while n_bins < self.seq_len:
                # read from the function generator stream
                streams = self.r.xread(stream_dict,
                                       block=0,
                                       count=self.seq_len - n_bins)
                ts_read = time.monotonic()
                _, stream_entries = streams[0]
                for self.data_id, entry_dict in stream_entries:
                    # load the input
                    window[0, n_bins, :] = np.frombuffer(entry_dict[input_field], dtype=input_dtype)
                    i_in = entry_dict[b'i']
                    # ts_in = entry_dict[b'ts']
                    ts_in = np.frombuffer(entry_dict[b'ts'], dtype=np.uint64)/1000000000
                    n_bins += 1
                stream_dict[input_stream] = self.data_id
            x = torch.from_numpy(window)
            # generate a prediction
            ts_before = time.monotonic()
            with torch.no_grad():
                y[:] = self.model(x)[0, -1, :]

            # write results to Redis
            ndt_entry['ts_after'] = time.monotonic()
            ndt_entry['ts_before'] = ts_before
            ndt_entry['ts_read'] = ts_read
            ndt_entry['i'] = i
            ndt_entry['i_in'] = i_in
            ndt_entry['ts_in'] = float(ts_in)
            ndt_entry['samples'] = y.numpy().tobytes() # y.detach().numpy().tobytes()
            ndt_entry['ts_add'] = time.monotonic()

            self.r.xadd('ndt', ndt_entry)

            # shift window along the seq_len axis
            window[0, 1:, :] = window[0, :-1, :]
            n_bins -= 1
            i += 1

    def terminate(self, sig, frame):
        logging.info('SIGINT received, Exiting')
        gc.collect()
        sys.exit(0)


if __name__ == "__main__":
    gc.disable()

    ### Setup Node
    ndt_node = NDTNode()

    ### Run main loop
    ndt_node.run()

    gc.collect()