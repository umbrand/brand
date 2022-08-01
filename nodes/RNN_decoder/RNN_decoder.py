#! /usr/bin/env python
import argparse
import torch
torch.set_num_threads(1)
import numpy as np
import time
import logging
import pickle
import yaml
import json
import os

from src.RNN_model import RNN
from pathlib import Path
from brand import BRANDNode

# REMOVE LATER
from sklearn.preprocessing import StandardScaler, MinMaxScaler

class runRNN(BRANDNode):
    """ A class for real-time Recurrent Neural Network
    Inference for BrainGate2 experiments.
    """

    def __init__(self):
        super().__init__()

        # Pull model paths from training YAML file
        yaml_path = self.parameters['model_pth']

        # Check if path is valid
        if not os.path.exists(yaml_path):
            raise FileNotFoundError("Specified file not found")

        with open(yaml_path, 'r') as file:
            self.model_paths = yaml.safe_load(file)

        # Define params for real-time decoding
        self.n_features = self.parameters['n_features']
        self.n_targets = self.parameters['n_targets']
        self.seq_len = self.parameters['seq_len']

        # Load model and scalars
        self.build()

        # Initialize output stream entry data
        self.output_stream = 'rnn_decoder'
        self.i = 0

        self.sync_dict = {'i': self.i}
        self.sync_dict_json = json.dumps(self.sync_dict)
        self.read_time = time.monotonic()
        self.before_pred_time = time.monotonic()

        self.decoder_entry = {
            'ts': time.monotonic(), 
            'sync': self.sync_dict_json.encode(),
            'read_time': self.read_time,
            'before_pred': self.before_pred_time,
            'y': np.zeros(self.n_targets).tobytes(),
            'i': self.i    
        }

        # Initialize input stream entry data
        self.input_entry = {
            'ts': time.monotonic(), 
            'sync': self.sync_dict_json.encode(),
            'samples': np.zeros(self.n_features).tobytes(),
            'i': self.i
        }

        # initialize IDs for the two Redis streams
        self.data_id = '$'
        self.param_id = '$'
        self.stream_dict = {b'func_generator': self.data_id}

        #Run dummy data through model to remove initial latency jump
        self.win = np.zeros((self.seq_len, self.n_features))
        dummy_thres = np.zeros(self.n_features)
        _, _ = self.predict(dummy_thres, self.win)

        logging.info('Starting RNN_decoder Node...')

    def build(self):
        """ Initializes RNN model and loads both the
        model weights and data scalars from training. 
        """

        # # Instantiate model
        # self.model = RNN(train=False)
                          
        # # load model weights
        # weight_path = Path(self.model_paths['real-time']['saved_weights'])
        # self.model.load_state_dict(torch.load(weight_path))

        # # IMPORTANT: set model to testing mode
        # self.model.eval()

        # # load data scalars                                         
        # scale_pth = Path(self.model_paths['real-time']['saved_scalars'])
        # with open(scale_pth, 'rb') as f:
        #     self.spike_scalar = pickle.load(f)
        #     self.vel_scalar = pickle.load(f)

        #-----------USE FOR TIMING TESTS AND TEST GRAPHS------------#

        # Instantiate model
        self.model = RNN(train=False)

        # IMPORTANT: set model to testing mode
        self.model.eval()

        # load scalars and fit with dummy data                                          
        self.spike_scalar = StandardScaler()
        self.vel_scalar = MinMaxScaler(feature_range=(-1,1))
        dum_spikes = np.zeros((1, self.n_features))
        dum_vels = np.zeros((1, self.n_targets))
        self.spike_scalar.fit(dum_spikes)
        self.vel_scalar.fit(dum_vels)

    def terminate(self, sig, frame):
        """ Terminates Redis instance after receiving
        SIGINT signal.
        """
        super().terminate(sig, frame)
    
    def predict(self, input, win):
        """ Produces target predictions from incoming
        spiking data.

        Parameters
        ----------
        input: numpy array
            Vector of raw spikes.
            Shape: (1, n_features)
            
        win: numpy array
            Window of binned spikes to use as
            input to the RNN.
            Shape: (seq_len, n_features)

        Returns
        -------
        out: numpy array
            target predictions from the RNN.
            Shape: ()
        
        window:
            shifted window of binned spikes with
            the new input appended to the end. 
            Shape: (seq_len, n_features)     
        """

        # create window of bins x features (15,256)
        window = win
        window[:-1, :] = window[1:, :]
        window[-1, :] = input

        # zscore normalize input
        norm_window = self.spike_scalar.transform(window)

        # create tensor and reshape as (1, 15, 256)
        model_input = torch.tensor(norm_window, dtype=torch.float)
        model_input = torch.unsqueeze(model_input, 0)

        # model inference
        with torch.no_grad():
            out = self.model(model_input)
            out = out.numpy()

        # rescale velocity predictions
        out = self.vel_scalar.inverse_transform(out)

        return out, window

    def run(self):
        """ Real-time loop that reads in stream of
        binned thresholds and writes out target
        prediction stream.
        """

        while True:
            # read from input stream
            streams = self.r.xread(self.stream_dict, block=0, count=1)
            self.read_time = time.monotonic()
            stream_name, stream_entries = streams[0]
            self.data_id, self.input_entry = stream_entries[0]
            self.stream_dict[b'func_generator'] = self.data_id

            ts_gen = np.frombuffer(self.input_entry[b'ts'], dtype=np.uint64) / 1000000000

            # load the input and generate a prediction
            x = np.frombuffer(self.input_entry[b'samples'], dtype=np.float64)
            self.before_pred_time = time.monotonic()
            y, self.win = self.predict(x, self.win)

            # Update sync value
            self.sync_dict = {'i': self.i}
            self.sync_dict_json = json.dumps(self.sync_dict)

            # Update stream entry
            self.decoder_entry = { 
            'sync': self.sync_dict_json.encode(),
            'ts_gen':  float(ts_gen),
            'read_time': self.read_time,
            'before_pred': self.before_pred_time,
            'y': y.tobytes(),
            'i': self.i,
            'ts': time.monotonic()    
            }

            # Write data to Redis
            self.r.xadd(self.output_stream, self.decoder_entry)

            # Update index
            self.i = self.i + 1 


if __name__ == "__main__":
    ### Setup Node
    decoder = runRNN()

    ### Run main loop
    decoder.run()