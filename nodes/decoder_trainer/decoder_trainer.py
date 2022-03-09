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
#
# need to allow for lags if wanted, looser alignment if we have samples coming in at different freqs
# 
# -- Kevin



###########################################
# Support Functions
###########################################
class timeval(Structure):
    """
    timeval struct from sys/time.h
    """
    _fields_ = [("tv_sec", c_long), ("tv_usec", c_long)]

# -----------------------------------------
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

# -----------------------------------------
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

# -----------------------------------------
def save_model(estimator, filepath, redis_conn):
    """
    Save a pkl representation of a scikit-learn model to the provided filepath,
    plus save the model to the redis instance

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
    
    with open(filepath, 'wb') as f:
        print(f"[decoder_builder.py] writing model to {filepath}")
        pickle.dump(model_info, f)

    # write a pickled version into redis, too. This will be supported for later usage
    pkl = pickle.dumps(model_info)
    redis_conn.xadd('decoder_model',{'pickled_model':pkl}) 


# -----------------------------------------
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

# -----------------------------------------
def lag_expand(array, numLags):
    """
    Takes an array, shifts it down, joins it to the original array.

    example with 2 lags:
                |1111|     |1111 0000 0000|  
                |2222|     |2222 1111 0000|
                |3333|  -> |3333 2222 1111|
                |4444|     |4444 3333 2222|
                |5555|     |5555 4444 3333|

    Parameters
    ----------
    array     : array to be shifted and joined
    numLags   : number of lags

    Returns
    -------
    lagArray  : new array
    """
    old0,old1    = array.shape # getting the input array shape
    newShape     = (old0, old1*(numLags+1)) # T+l x N*l
    lagArray     = np.zeros(newShape) # empty array

    for lag in range(0,numLags+1):
        lagArray[lag:, lag*old1:(lag+1)*old1] = array[:old0-lag,:]

    return lagArray
        



###########################################
# Loading in settings etc
###########################################

YAML_FILE = sys.argv[1] if len(sys.argv) > 1 else 'decoder_trainer.yaml'
NAME = 'decoder_trainer'

# set up logging
loglevel = get_node_parameter_value(YAML_FILE, NAME, 'log')
numeric_level = getattr(logging, loglevel.upper(), None)

if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(format=f'%(levelname)s:[{NAME}]:%(message)s',
                    level=numeric_level)

# %%
r = initializeRedisFromYAML(YAML_FILE, NAME)


print(f"[{NAME}] Parsing data")
###########################################
# Load Data
###########################################
trainStream = get_node_parameter_value(YAML_FILE, NAME, 'trainStream')


# xread STREAMS thresholdCrossings 0
reply = r.xread(streams={trainStream: 0})
stream_name, entries = reply[0] # it comes back in a list!
entry_list = []
trainSamp = get_node_parameter_value(YAML_FILE, NAME, 'trainSamp')
trainTS = get_node_parameter_value(YAML_FILE, NAME, 'trainTS')
# parse the returned list -- each entry is a dict, the whole thing is a list
for entry_id, entry_dict in entries:
    entry_dict[trainSamp.encode('utf-8')] = np.frombuffer(entry_dict[trainSamp.encode('utf-8')],
                                             dtype=np.short)
    entry_dict[trainTS.encode('utf-8')] = np.frombuffer(entry_dict[trainTS.encode('utf-8')],
                                              dtype=np.uint32).item()
    entry_dict[b'id'] = entry_id
    entry_list.append(entry_dict) # create a list entry of each dictionary 

spike_df = pd.DataFrame(entry_list) # turn that list of dictionaries into a pandas dataframe
spike_df.rename(columns={col: col.decode() # and get rid of the byte encoding of the columns
                         for col in spike_df.columns},
                inplace=True)

# Load cursor kinematics
# XREAD COUNT 1 STREAMS taskInput 0
targetStream = get_node_parameter_value(YAML_FILE, NAME, 'targetStream')
targetSamples = get_node_parameter_value(YAML_FILE, NAME, 'targetSamp')
targetTS = get_node_parameter_value(YAML_FILE, NAME, 'targetTS')
reply = r.xread(streams={targetStream: 0})
stream_name, entries = reply[0]
entry_list = []
# parse the data into a list of dictionaries -- each packet is its own dictionary
for entry_id, entry_dict in entries:
    entry_dict[bytes(targetTS, 'utf-8')] = np.frombuffer(entry_dict[bytes(targetTS, 'utf-8')],
                                              dtype=np.uint32).item()
    entry_dict[bytes(targetSamples, 'utf-8')] = np.frombuffer(entry_dict[bytes(targetSamples, 'utf-8')],
                                           dtype=np.short)
    entry_list.append(entry_dict)

kin_df = pd.DataFrame(entry_list)
kin_df.rename(columns={col: col.decode()
                       for col in kin_df.columns},
              inplace=True)

# separating out x and y position for the moment, but might be worth just keeping them...
pos = np.stack(kin_df[targetSamples])
kin_df['x_pos'] = pos[:, 1] # touchpad is sensor 0, so x is sensor 1 and y is sensor 2
kin_df['y_pos'] = pos[:, 2]

# ----------------------------------------------------------
# align spikes and target signal 
print(f"[{NAME}] Binning and aligning data")

# first align the beginning
if kin_df.iloc[0][targetTS] < spike_df.iloc[0][trainTS]:
    delay = np.argmin((kin_df[targetTS] - spike_df.iloc[0][trainTS])**2) # lag for crossings to start
    kin_df = kin_df.iloc[delay:]
else:
    delay = np.argmin((spike_df[trainTS] - kin_df.iloc[0][targetTS])**2) # lag for crossings to start
    spike_df = spike_df.iloc[delay:]

# put things into an ndarray rather than a pandas dataframe
spikes = np.stack(spike_df['crossings'].values) # convert to an ndarray
kin = kin_df[['x_pos', 'y_pos']].values # same

# bin train and target datasets
sample_rate = get_node_parameter_value(YAML_FILE, NAME, 'sample_rate')  # Hz
bin_size = get_node_parameter_value(YAML_FILE, NAME, 'bin_size') # this assumes firing rates are the same. Bad idea...
binned_spikes = bin_data(spikes, bin_size)
binned_kin = bin_data(kin, bin_size)

# add lags to allow for historical info to pass through:
lag_num = get_node_parameter_value(YAML_FILE, NAME, 'num_lags')
binned_spikes = lag_expand(binned_spikes, lag_num)


# trim to match lengths
if binned_kin.shape[0] > binned_spikes.shape[0]:
    binned_kin = binned_kin[:binned_spikes.shape[0]]
else:
    binned_spikes = binned_spikes[:binned_kin.shape[0]]

    
# train a decoder
print(f"[{NAME}] Training Decoder")
mdl = Ridge()
mdl.fit(binned_spikes, binned_kin)

# give some info to the screen...
print(f"[{NAME}] Linear decoder built with average Cooeficient of Determination of {mdl.score(binned_spikes, binned_kin)}")

# %%
filepath = get_node_parameter_value(YAML_FILE, NAME, 'model_path')
save_model(mdl, filepath, r)
logging.info(f'Saved decoder to {filepath}')

# close Redis connection
r.close()
