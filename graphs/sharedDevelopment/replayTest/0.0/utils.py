from ctypes import Structure, c_long
from datetime import datetime

import numpy as np
from scipy import signal


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


def decode_field(entry, stream, field, stream_spec):
    dtype = stream_spec[stream][field]
    if dtype == 'str':
        decoded_entry = entry.decode()
    elif dtype == 'float':
        decoded_entry = float(entry)
    elif dtype == 'bool':
        decoded_entry = bool(entry)
    elif dtype == 'timeval':
        n_bytes = len(entry)
        n_items = int(n_bytes / 16)
        if n_items == 1:
            decoded_entry = timeval_to_datetime(entry).timestamp()
        else:
            vals = np.zeros(n_items)
            for ii in range(n_items):
                a, b = (ii * 16, (ii + 1) * 16)
                vals[ii] = timeval_to_datetime(entry[a:b]).timestamp()
    else:
        decoded_entry = np.frombuffer(entry, dtype=dtype)
        if len(decoded_entry) == 1:
            decoded_entry = decoded_entry.item()
    return decoded_entry


def get_lagged_features(data, n_history: int = 4):
    """
    Lag the data along the time axis. Stack the lagged versions of the data
    along the feature axis.

    Parameters
    ----------
    data : array of shape (n_samples, n_features)
        Data to be lagged
    n_history : int, optional
        Number of bins of history to include in the lagged data, by default 4

    Returns
    -------
    lagged_features : array of shape (n_samples, n_history * n_features)
        Lagged version of the original data
    """
    assert n_history >= 1, 'n_history must be greater than or equal to 1'
    lags = [None] * n_history
    for i in range(n_history):
        lags[i] = np.zeros_like(data)
        lags[i][i:, :] = data[:-i, :] if i > 0 else data
    lagged_features = np.hstack(lags)
    return lagged_features


def smooth_data(data, bin_size, gauss_width):
    """
    Smooth data with a Gaussian kernel

    Parameters
    ----------
    data : np.ndarray
        Array of data with shape (n_bins, n_features)
    bin_size : int
        Bin size of data (in ms)
    gauss_width : int
        Standard deviation of the Gaussian kernel (in ms)
    """
    smoothed_data = np.empty_like(data)

    gauss_bin_std = gauss_width / bin_size
    win_len = int(6 * gauss_bin_std)

    window = signal.gaussian(win_len, gauss_bin_std, sym=True)
    window /= np.sum(window)

    n_chans = data.shape[1]
    for ich in range(n_chans):
        smoothed_data[:, ich] = signal.convolve(data[:, ich],
                                                window,
                                                mode='same')

    return smoothed_data
