#! /usr/bin/env python
# _*_ coding: utf-8 -*-
# exportNWB.py
"""
exportNWB.py
Takes data from a dump.rdb and a graph to export it as an NWB file for
analysis in Python and MATLAB
Requires first input be the RDB dump and the second be the graph YAML
@author Sam Nason-Tomaszewski, adapted for supervisor by Mattia Rigotti
"""

import json
import logging
import os
import signal
import sys
from datetime import datetime

import numpy as np
import yaml
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.behavior import Position
from redis import ConnectionError, Redis

###############################################
# Initialize script
###############################################
NAME = 'exportNWB'
BATCH_SIZE = 1000  # max number of samples to grab from redis at a time

rdb_file = sys.argv[1]

redis_host = sys.argv[2]
redis_port = sys.argv[3]

save_filename = os.path.splitext(rdb_file)[0]
save_filepath = sys.argv[4]

devices_path = os.path.join(os.getenv('BRAND_BASE_DIR'),
                            '../Data/devices.yaml')

# set up logging
loglevel = 'INFO'
numeric_level = getattr(logging, loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)
logging.basicConfig(format=f'[{NAME}] %(levelname)s: %(message)s',
                    level=numeric_level)


#############################################################
## setting up clean exit code
#############################################################
def signal_handler(sig, frame):  # setup the clean exit code with a warning
    logging.info('SIGINT received. Exiting...')
    sys.exit(0)


# place the sigint signal handler
signal.signal(signal.SIGINT, signal_handler)


###############################################
# Helper functions
###############################################
def add_stream_sync_timeseries(nwbfile, stream, time_data):
    """
    Creates an sync timeseries representing the
    system (monotonic), redis, and other sync times
    at which each stream had an entry
    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile in which to store the sync timeseries
    stream : str
        The name of the stream
    stream_data : dict
        The stream's data containing times
    """

    time_data_stack = {
        k: time_data[k]
        for k in time_data if k != 'sync_timestamps'
    }
    column_order_string = ', '.join(
        [k for k in time_data.keys() if k != 'sync_timestamps'])

    sync_timeseries = TimeSeries(
        name=f'{stream}_sync',
        data=np.stack(list(time_data_stack.values()), axis=1),
        unit='seconds',
        timestamps=time_data['sync_timestamps'],
        comments=f'Column order: {column_order_string}',
        description=f'Syncing timestamps for the {stream} stream')

    nwbfile.add_acquisition(sync_timeseries)


def create_nwb_trials(nwbfile, stream, stream_data, var_params):
    """
    Adds trials to the nwbfile
    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile in which to store the trials
    stream : str
        The name of the stream sourcing the data
    stream_data : dict
        The stream's data
    var_params : dict
        NWB storage parameters for the data
    """

    # get key for the trial_state variable
    for var in var_params:
        if 'nwb' in var_params[var] and var_params[var][
                'nwb'] is not None and 'trial_state' in var_params[var]['nwb']:
            trial_state = var_params[var]['nwb']['trial_state']

    # first get trial indicators
    start_trial_indicators = var_params[trial_state]['nwb'][
        'start_trial_indicators']
    end_trial_indicators = var_params[trial_state]['nwb'][
        'end_trial_indicators']
    other_trial_indicators = var_params[trial_state]['nwb'][
        'other_trial_indicators']

    # get data indices corresponding to trial states
    starts = np.isin(stream_data['state']['data'], start_trial_indicators)
    start_inds = stream_data['state']['data'][starts]
    ends = np.isin(stream_data['state']['data'], end_trial_indicators)
    end_inds = stream_data['state']['data'][ends]
    others = {
        k: np.isin(stream_data['state']['data'], k)
        for k in other_trial_indicators
    }

    # get sync timestamps
    start_times = stream_data[trial_state]['sync_timestamps'][starts[:, 0]]
    end_times = stream_data[trial_state]['sync_timestamps'][ends[:, 0]]
    other_times = {
        k: stream_data[trial_state]['sync_timestamps'][others[k][:, 0]]
        for k in others
    }

    # remove final start_time and relevant other_times if stopped during trial
    # do the if statement because will likely be faster considering the loop for other_times
    if start_times.shape[0] != end_times.shape[0]:
        start_times = start_times[:end_times.shape[0]]
        other_times = {
            k: other_times[k][other_times[k] < end_times[-1]]
            for k in other_times
        }

    # add a column for our other trial milestones
    for k in other_times:
        nwbfile.add_trial_column(
            name=k,
            description=var_params[trial_state]['nwb'][k + '_description'])

    for s_time, e_time, s_ind, e_ind in zip(start_times, end_times, start_inds,
                                            end_inds):
        # first find the other_times corresponding to the current trial
        trial_other_times = {
            k: other_times[k][np.logical_and(other_times[k] >= s_time,
                                             other_times[k] <= e_time)]
            for k in other_times
        }
        trial_other_times = {
            k: np.nan
            if trial_other_times[k].size == 0 else trial_other_times[k][0]
            for k in trial_other_times
        }

        # now create the trial
        nwbfile.add_trial(start_time=s_time,
                          stop_time=e_time,
                          start_indicator=s_ind,
                          stop_indicator=e_ind,
                          **trial_other_times)


def add_nwb_trial_info(nwbfile, stream, stream_data, var_params):
    """
    Adds trial information to the trials table. The code
    below assumes the trials table has already been
    generated in nwbfile.
    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile in which to store trial information
    stream : str
        The name of the stream sourcing the data
    stream_data : dict
        The stream's data
    var_params : dict
        NWB storage parameters
    """

    num_trials = len(nwbfile.trials)

    for var in stream_data:
        var_data_per_trial = np.empty((num_trials),
                                      dtype=stream_data[var]['data'].dtype)

        # loop through trials to get one entry of var per trial
        for id, trial in enumerate(nwbfile.trials):
            var_data_in_trial = stream_data[var]['data'][np.logical_and(
                stream_data[var]['sync_timestamps'] >= trial.start_time.values,
                stream_data[var]['sync_timestamps'] <= trial.stop_time.values)]
            var_data_per_trial[
                id] = np.nan if var_data_in_trial.size == 0 else var_data_in_trial[
                    0]

        nwbfile.add_trial_column(
            name=stream + '_' + var,
            description=var_params[var]['nwb']['description'],
            data=var_data_per_trial)


def create_nwb_position(nwbfile, stream, stream_data, var_params):
    """
    Generates a position container
    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile in which to store the series
    stream : str
        The name of the stream sourcing the data
    stream_data : dict
        The stream's data
    var_params : dict
        NWB storage parameters for each variable
    """
    pos = Position(name=stream)

    for var in stream_data:
        pos.create_spatial_series(
            name=var,
            data=stream_data[var]['data'],
            timestamps=stream_data[var]['sync_timestamps'],
            **var_params[var]['nwb'])
    nwbfile.add_acquisition(pos)


def create_nwb_unitspiketimes(nwbfile, stream, stream_data, var_params):
    """
    Adds spike times to pre-existing units
    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile in which to store the series
    stream : str
        The name of the stream sourcing the data
    stream_data : dict
        The stream's data
    var_params : dict
        NWB storage parameters for each variable
    """

    # get key for the trial_state variable
    for var in var_params:
        if var_params[var]['nwb'] is not None and 'crossings' in var_params[
                var]['nwb']:
            crossings_var = var_params[var]['nwb']['crossings']

    for electrode in range(stream_data[crossings_var]['data'].shape[1]):
        nwbfile.add_unit(
            electrodes=[electrode],
            electrode_group=nwbfile.electrode_groups['array 1'],
            spike_times=stream_data[crossings_var]['sync_timestamps'][
                stream_data[crossings_var]['data'][:, electrode].astype(bool)],
            stream=stream)


def create_nwb_timeseries(nwbfile, stream, stream_data, var_params):
    """
    Generates a time series container
    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile in which to store the series
    stream : str
        The name of the stream sourcing the data
    stream_data : dict
        The stream's data
    var_params : dict
        NWB storage parameters for each variable
    """
    var = list(stream_data.keys())[0]

    timeseries = TimeSeries(name=stream,
                            data=stream_data[var]['data'],
                            unit=var_params[var]['nwb']['unit'],
                            timestamps=stream_data[var]['sync_timestamps'],
                            description=var_params[var]['nwb']['description'])

    nwbfile.add_acquisition(timeseries)


def get_stream_source(graph_data, stream):
    """
    Returns the node sourcing a redis stream.
    Parameters
    ----------
    graph_data : dict
        supergraph dictionary
    stream : str
        name of the stream whose source to search
    Returns
    -------
    str
        name of the node sourcing stream
    """
    for node in graph_data['nodes']:
        if stream in graph_data['nodes'][node]['redis_outputs']:
            return graph_data['nodes'][node]['name']
    return None


def get_node_module(graph_data, node_name):
    """
    Get the module name from the node name in a yaml file
    Parameters
    ----------
    graph_data : dict
        supergraph dictionary
    node_name : str
        Name of the node to use
    Returns
    -------
    str
        Module name for node
    """
    for node in graph_data['nodes']:
        if graph_data['nodes'][node]['name'] == node_name:
            return graph_data['nodes'][node]['module']


def get_stream_configuration(yaml_path, stream):
    """
    Return information about a stream, as
    defined by the node's yaml file
    Parameters
    ----------
    yaml_path : str
        path of the node YAML file
    stream    : str
        name of the stream we're inspecting
    Returns:
    dict
        a dictionary with stream configuration 
    """
    with open(yaml_path, 'r') as f:
        yamlData = yaml.safe_load(f)
    inputs_and_outputs = yamlData['RedisStreams']['value']
    if inputs_and_outputs is not None:
        for io in inputs_and_outputs.keys():
            if inputs_and_outputs[
                    io] is not None and stream in inputs_and_outputs[io].keys(
                    ):
                return inputs_and_outputs[io][stream]
    return {}


###############################################
# Connect to redis
###############################################
try:
    logging.info(f"Connecting to Redis at {redis_host}:{redis_port}...")
    r = Redis(redis_host, redis_port, retry_on_timeout=True)
    r.ping()
except ConnectionError as e:
    logging.error(f"Error with Redis connection, check again: {e}")
    sys.exit(1)
except:
    logging.error('Failed to connect to Redis. Exiting.')
    sys.exit(1)

logging.info('Redis connection successful.')

###############################################
# Load all stream and NWB info
# do outside of main loop for eventual translation to real-time
###############################################

try:
    model_stream_entry = r.xrevrange(b'supergraph_stream', '+', '-', 1)[0]
except IndexError as e:
    logging.error(
        f"No model published to supergraph_stream in Redis. Exiting.")
    sys.exit(1)

entry_id, entry_dict = model_stream_entry
model_data = json.loads(entry_dict[b'data'].decode())

# Get graph name
graph_name = model_data['graph_name']

# Get timing keys
sync_key = 'sync'  #graph_timing['SyncKey']
time_key = 'ts'  #graph_timing['TimeKey']

## Get exportnwb_io
exportnwb_io = {'redis_inputs': {}, 'redis_outputs': {}}

redis_inputs = model_data['derivatives']['exportNWB']['redis_inputs']
redis_outputs = model_data['derivatives']['exportNWB']['redis_outputs']
if type(redis_inputs) is str:
    redis_inputs = [redis_inputs]
if type(redis_outputs) is str:
    redis_outputs = [redis_outputs]

exportnwb_io['redis_inputs'] = redis_inputs
exportnwb_io['redis_outputs'] = redis_outputs

exportnwb_enables = model_data['derivatives']['exportNWB']['parameters'][
    'enable_nwb']

stream_dict = {
    k: {
        'source': None,
        'source_yaml': None,
        'config': {},
        'last_id': b'-'
    }
    for k in exportnwb_io['redis_inputs']
}
stream_to_del = []
for stream in stream_dict:
    stream_dict[stream]['source'] = get_stream_source(model_data, stream)
    if stream_dict[stream]['source'] is None:
        logging.error(f'Wrong graph! Source node not found! Stream: {stream}')
        stream_to_del.append(stream)
    else:
        stream_dict[stream]['source'] = stream_dict[stream]['source'].rsplit(
            '.', 1)[0]  # gets node name even if filetype included in name
        stream_dict[stream]['source_yaml'] = os.path.join(
            os.getenv('BRAND_BASE_DIR'),
            '../brand-modules',
            get_node_module(model_data, stream_dict[stream]['source']),
            'nodes', stream_dict[stream]['source'],
            stream_dict[stream]['source'] + '.yaml')
        stream_dict[stream]['config'] = get_stream_configuration(
            stream_dict[stream]['source_yaml'], stream)

        if 'enable_nwb' in stream_dict[stream][
                'config'] and 'type_nwb' in stream_dict[stream]['config']:
            if stream in exportnwb_enables:
                stream_dict[stream]['config'][
                    'enable_nwb'] = exportnwb_enables[stream]
            else:
                logging.info(f'Using default NWB enable. Stream: {stream}')
        else:
            logging.warning(
                f'Invalid NWB parameters. \'enable_nwb\' and \'type_nwb\' are required. Stream: {stream}'
            )
            stream_dict[stream]['config']['enable_nwb'] = False

# remove streams not in the graph
for stream in stream_to_del:
    del (stream_dict[stream])

# find 'Trial', 'Trial_Info', and 'Spike_Times' streams
trial_stream = None
trial_info_stream = None
spike_times_streams = []
for stream in stream_dict:
    # if the stream is of type 'Trial'
    if stream_dict[stream]['config']['enable_nwb'] and stream_dict[stream][
            'config']['type_nwb'] == 'Trial':
        if trial_stream == None:
            trial_stream = stream
        else:
            logging.error(
                f'Multiple Trial streams, only one allowed! Stream: {stream}')
    # if the stream is of type 'Trial_Info'
    elif stream_dict[stream]['config']['enable_nwb'] and stream_dict[stream][
            'config']['type_nwb'] == 'TrialInfo':
        trial_info_stream = stream
    elif stream_dict[stream]['config']['enable_nwb'] and stream_dict[stream][
            'config']['type_nwb'] == 'SpikeTimes':
        spike_times_streams.append(stream)

# guarantee there is a 'Trial' stream if we have a 'Trial_Info' stream
if trial_info_stream is not None and trial_stream == None:
    logging.error('Trial_Info stream exists but no Trial stream!')

# guarantee the 'Trial' stream is processed first
has_trial_stream = False
if trial_stream is not None:
    key_order = [k for k in stream_dict if k not in [trial_stream]]
    key_order.insert(0, trial_stream)
    stream_dict = {k: stream_dict[k] for k in key_order}
    has_trial_stream = True

###############################################
# Prepare NWB file
###############################################

# get metadata
graph_meta = model_data['derivatives']['exportNWB']['parameters']
participant_metadata_file = graph_meta['participant_file']
with open(participant_metadata_file, 'r') as f:
    yamlData = yaml.safe_load(f)
    participant_metadata = yamlData['metadata']
    participant_implants = yamlData['implants']

# get devices information
with open(devices_path, 'r') as f:
    devices = yaml.safe_load(f)

# TODO autogenerate these inputs to represent block information
nwbfile = NWBFile(session_description=graph_meta['description'],
                  identifier=graph_name,
                  session_start_time=datetime.today(),
                  file_create_date=datetime.today())

# add trial column containing the stream's name that sourced each trial state change
if has_trial_stream:
    nwbfile.add_trial_column(
        name='start_indicator',
        description='list of the indicators used to start the trial')
    nwbfile.add_trial_column(
        name='stop_indicator',
        description='list of the indicators used to stop the trial')

# add unit column containing the stream's name that sourced the crossings
if spike_times_streams:
    nwbfile.add_unit_column(
        name='stream',
        description='Name of stream providing threshold crossings')

# create devices, create electrode groups, and create electrodes
for implant in participant_implants:
    for device_entry in devices:
        if implant['device'] == device_entry['name']:
            device = device_entry
            break

    if device['name'] in nwbfile.devices:
        nwb_device = nwbfile.devices[implant['device']]
    else:
        nwb_device = nwbfile.create_device(name=device['name'],
                                           description=device['description'],
                                           manufacturer=device['manufacturer'])

    nwb_group = nwbfile.create_electrode_group(
        name=implant['name'],
        description=f'{implant["device"]} connected to {implant["connector"]}',
        location=implant['location'],
        device=nwb_device,
        position=implant['position'])

    # TODO autogenerate from subject implant (array files from Blackrock)
    # for now, just dummy electrode assignment
    for electrode in range(device['electrode_qty']):
        nwbfile.add_electrode(x=float(electrode),
                              y=float(electrode),
                              z=float(electrode),
                              imp=float(electrode),
                              location=implant['location'],
                              filtering='0.3 Hz to 7.5 kHz Butterworth',
                              group=nwb_group)

###############################################
# Pull data from streams and write to NWB
###############################################

# set up dictionary of NWB writing functions
nwb_funcs = {
    'Trial': create_nwb_trials,
    'TrialInfo': add_nwb_trial_info,
    'Position': create_nwb_position,
    'SpikeTimes': create_nwb_unitspiketimes,
    'TimeSeries': create_nwb_timeseries
}

# loop through streams to extract data
for stream in stream_dict:
    # checks the ENABLE_NWB parameter is set to true
    if stream_dict[stream]['config']['enable_nwb']:

        logging.info(f'Extracting data. Stream: {stream}')

        ###################################
        # first extract the data from redis
        ###################################
        stream_len = r.xlen(stream)
        entry_count = 0  # counter for stream entries
        sync_name = stream_dict[stream]['config']['sync'][0]

        # stream_data:
        #   data:               store extracted data
        #                       dim0 = number of stream entries * number of samples per entry
        #                       dim1 = number of channels
        #   sync_timestamps:    store sync timestamps for each piece of extracted data
        #                       dim0 = number of stream entries * number of samples per entry
        #   sample_count:       track how many samples have been counted for each key
        stream_data = {
            k: {
                'data':
                np.empty((stream_len *
                          stream_dict[stream]['config'][k]['samp_per_stream'],
                          stream_dict[stream]['config'][k]['chan_per_stream']),
                         dtype=object
                         if stream_dict[stream]['config'][k]['sample_type']
                         == 'str' else stream_dict[stream]['config'][k]
                         ['sample_type']),  # ugly, but need to handle strings
                'sync_timestamps':
                np.empty(stream_len *
                         stream_dict[stream]['config'][k]['samp_per_stream'],
                         dtype=np.double),
                'sample_count':
                0
            }
            for k in stream_dict[stream]['config']
            if (k not in ['enable_nwb', 'type_nwb', 'sync']
                and 'nwb' in stream_dict[stream]['config'][k])
        }

        # time_data:
        #   sync_timestamps:    store sync timestamps for each piece of extracted data
        #                       dim0 = number of stream entries
        #   monotonic_ts:       store the monotonic clock timestamp
        #                       dim0 = number of stream entries
        #   redis_ts:           store the redis clock timestamp
        #                       dim0 = number of stream entries
        #   <other>:            store the sync timestamps for other, non-blocking incoming syncs
        time_data = {
            'sync_timestamps': np.empty(stream_len,
                                        dtype=np.double),  # sync timestamps
            'monotonic_ts': np.empty(stream_len,
                                     dtype=np.double),  # monotonic timestamp
            'redis_ts': np.empty(stream_len, dtype=np.double)
        }  # redis timestamp
        time_data.update({
            k: np.empty(stream_len, dtype=np.double)
            for k in stream_dict[stream]['config']['sync']
            if k != stream_dict[stream]['config']['sync'][0]
        })

        while entry_count < stream_len:
            stream_read = r.xrange(stream,
                                   min=stream_dict[stream]['last_id'],
                                   count=BATCH_SIZE)

            for ind, entry in enumerate(stream_read):
                sync_data = json.loads(entry[1][sync_key.encode()])
                time_data['sync_timestamps'][entry_count + ind] = float(
                    sync_data[sync_name]
                ) / 1000  # get blocked sync timestamp in ms, convert to seconds
                time_data['monotonic_ts'][entry_count + ind] = float(
                    entry[1][time_key.encode()])
                time_data['redis_ts'][entry_count + ind] = float(
                    entry[0].decode('utf-8').split('-')[0]) / 1000

                # get other sync signals for this entry
                for sync in sync_data:
                    if sync in sync_name:
                        continue
                    time_data[sync][entry_count +
                                    ind] = float(entry[sync]) / 1000

                for var in stream_data:
                    if 'nwb' not in stream_dict[stream]['config'][var].keys():
                        continue
                    var_config = stream_dict[stream]['config'][var]
                    batch_idx = list(
                        range(
                            stream_data[var]['sample_count'],
                            stream_data[var]['sample_count'] +
                            var_config['samp_per_stream']))
                    if stream_dict[stream]['config'][var][
                            'sample_type'] == 'str':
                        stream_data[var]['data'][batch_idx, :] = entry[1][
                            var.encode()].decode('utf-8')
                    else:
                        stream_data[var]['data'][batch_idx, :] = np.frombuffer(
                            entry[1][var.encode()],
                            dtype=stream_data[var]['data'].dtype).reshape([
                                var_config['samp_per_stream'],
                                var_config['chan_per_stream']
                            ])
                    stream_data[var]['sync_timestamps'][batch_idx] = time_data[
                        'sync_timestamps'][entry_count + ind]
                    stream_data[var]['sample_count'] += var_config[
                        'samp_per_stream']

            last_id = stream_read[-1][0].decode('utf-8').split(
                '-'
            )  # get the last entry id, change from byte to string, split by the '-' in the middle
            stream_dict[stream]['last_id'] = last_id[0] + '-' + str(
                int(last_id[1]) +
                1)  # increment the sequence number, recombine
            entry_count += len(stream_read)

        #####################################
        # now append the data to the NWB file
        #####################################
        add_stream_sync_timeseries(nwbfile, stream, time_data)

        nwb_funcs[stream_dict[stream]['config']['type_nwb']](
            nwbfile, stream, stream_data, {
                k: stream_dict[stream]['config'][k]
                for k in stream_dict[stream]['config']
                if k not in ['enable_nwb', 'type_nwb', 'sync']
            })

        logging.info(f'Export completed. Stream: {stream}')

###############################################
# Save the NWB object to file
###############################################
save_filename = save_filename + '.nwb'

if not os.path.exists(save_filepath):
    os.makedirs(save_filepath)

save_path = os.path.join(save_filepath, save_filename)

# save the file
logging.info(f'Saving NWB file to: {save_path}')
with NWBHDF5IO(save_path, 'w') as io:
    io.write(nwbfile)
