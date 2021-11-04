from ctypes import Structure, c_long
from datetime import datetime
import numpy as np


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
