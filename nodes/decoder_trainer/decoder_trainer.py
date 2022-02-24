#!/usr/bin/env python
# -*- coding: utf-8 -*-
# decoder_trainer.py
# %%
import json # likely going to switch to pickle
import pickle
import logging
import sys
from ctypes import Structure, c_long
from datetime import datetime

import numpy as np
import pandas as pd
from brand import get_node_parameter_value, initializeRedisFromYAML
from sklearn.linear_model import Ridge


# Current status:
# For some reason it is bringing the 96xT data in as a 96*T one dimensional vector.
# This needs to change if we're going to actually be able to do predictions.
#
# 1. set up reshape properly
# 2. allow for lags to have history in the ridge regression
# 
# -- Kevin





class timeval(Structure):
    """
    timeval struct from sys/time.h
    """
    _fields_ = [("tv_sec", c_long), ("tv_usec", c_long)]


def timeval_to_datetime(val):
    """
    Convert a C timeval object to a Python datetime

    Parameters
    ----------
    val : bytes
        timeval object encoded as bytes

    Returns
    -------
    datetime
        Python datetime object
    """
    ts = timeval.from_buffer_copy(val)
    timestamp = datetime.fromtimestamp(ts.tv_sec + ts.tv_usec * 1e-6)
    return timestamp


def bin_data(data, binsize=5):
    """
    Bin data according to the provided bin size

    Parameters
    ----------
    data : numpy.ndarray of shape (n_samples, n_features)
        data to be binned
    binsize : int, optional
        samples per bin, by default 5

    Returns
    -------
    numpy.ndarray of shape (n_samples // binsize, n_features)
        binned data
    """
    end = binsize * (data.shape[0] // binsize)
    binned_data = data[:end, :].reshape(data.shape[0] // binsize, binsize,
                                        data.shape[1]).mean(axis=1)
    return binned_data


def save_model(estimator, filepath):
    """
    Save a pkl representation of a scikit-learn model to the provided filepath

    Parameters
    ----------
    estimator : estimator object
        Trained sklearn estimator
    filepath : str
        path to use when saving the model
    """
    model_info = {}
    model_info['params'] = estimator.get_params()
    model_info['attr'] = {}
    for key, val in estimator.__dict__.items():
        if key.endswith('_'):
            if type(val) is np.ndarray:
                val = val.tolist()
            model_info['attr'][key] = val
    with open(filepath, 'w') as f:
        pickle.dump(model_info, f, indent=4)


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


YAML_FILE = sys.argv[1] if len(sys.argv) > 1 else 'decoder_trainer.yaml'
NAME = 'decoder_trainer'

# set up logging
loglevel = get_node_parameter_value(YAML_FILE, NAME, 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format=f'%(levelname)s:{NAME}:%(message)s',
                    level=numeric_level)

# %%
r = initializeRedisFromYAML(YAML_FILE, NAME)

# %%
# Load Neural Data
# xread STREAMS thresholdCrossings 0

i_stream = get_node_parameter_value(YAML_FILE, NAME, 'trainStream')
reply = r.xread(streams={i_stream: 0})

stream_name, entries = reply[0]
entry_list = []
trainSamp = get_node_parameter_value(YAML_FILE, NAME, 'trainSamp')
trainTS = get_node_parameter_value(YAML_FILE, NAME, 'trainTS')
for entry_id, entry_dict in entries:
    entry_dict[trainSamp] = np.frombuffer(entry_dict[trainSamp],
                                             dtype=np.short)
    entry_dict[trainTS] = np.frombuffer(entry_dict[trainTS],
                                              dtype=np.uint32).item()
    entry_dict[b'id'] = entry_id
    entry_list.append(entry_dict)

spike_df = pd.DataFrame(entry_list)
spike_df.rename(columns={col: col.decode()
                         for col in spike_df.columns},
                inplace=True)


# %%
# Load cursor kinematics
# XREAD COUNT 1 STREAMS taskInput 0
targetStream = get_node_parameter_value(YAML_FILE, NAME, 'targetStream')
targetSamples = get_node_parameter_value(YAML_FILE, NAME, 'targetSamp')
reply = r.xread(streams={targetStream: 0})
stream_name, entries = reply[0]
entry_list = []

for entry_id, entry_dict in entries:
    entry_dict[b'timestamps'] = np.frombuffer(entry_dict[b'timestamps'],
                                              dtype=np.uint32).item()
    entry_dict[b'BRANDS_time'] = timeval_to_datetime(
        entry_dict[b'BRANDS_time']).timestamp()
    entry_dict[b'udp_recv_time'] = timeval_to_datetime(
        entry_dict[b'udp_recv_time']).timestamp()
    entry_dict[targetSamples] = np.frombuffer(entry_dict[targetSamples],
                                           dtype=np.short)
    entry_list.append(entry_dict)

kin_df = pd.DataFrame(entry_list)
kin_df.rename(columns={col: col.decode()
                       for col in kin_df.columns},
              inplace=True)

pos = np.stack(kin_df[targetSamples])
kin_df['x_pos'] = pos[:, 1] # touchpad is sensor 0, so x is sensor 1 and y is sensor 2
kin_df['y_pos'] = pos[:, 2]

# ----------------------------------------------------------
# align spikes and target signal 

# first align the beginning
if kin_df.iloc[0][targetTS] < spike_df.iloc[0][trainTS]:
    lag = np.where(kin_df[targetTS] == spike_df.iloc[0][trainTS]) # lag for crossings to start
    kin_df = kin_df.iloc[lag]
else
    lag = np.where(spike_df[trainTS] == kin_df.iloc[0][targetTS]) # lag for crossings to start
    spike_df = spike_df.iloc[lag]

# trim to match lengths
if len(kin_df) > len(spike_df):
    kin_df = kin_df.iloc[:len(spike_df)]
else:
    spike_df = spike_df.iloc[:len(kin_df)]
    

# bin train and target datasets
sample_rate = get_node_parameter_value(YAML_FILE, NAME, 'sample_rate')  # Hz
binsize = get_node_parameter_value(YAML_FILE, NAME, 'binsize')

spikes = np.stack(spike_df[trainSamp].values)
binned_spikes = bin_data(spikes, binsize)

binned_kin = bin_data(


# %%
# define the decoder inputs
X = np.stack(spike_df['crossings'].values)
y = kin_df[['x_pos', 'y_pos']].values

# %%
# train a decoder
mdl = Ridge()
mdl.fit(X, y)

# %%
filepath = get_node_parameter_value(YAML_FILE, NAME, 'model_path')
save_model(mdl, filepath)
logging.info(f'Saved decoder to {filepath}')
# %%
