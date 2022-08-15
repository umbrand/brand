import ctypes
import time
from ctypes import Structure, c_long, pointer

TIMER_ABSTIME = 1
libc = ctypes.CDLL('libc.so.6')


class timespec(Structure):
    """
    timespec struct from sys/time.h
    """
    _fields_ = [("tv_sec", c_long), ("tv_nsec", c_long)]


def clock_nanosleep(time_ns, clock=time.CLOCK_REALTIME):
    """
    Sleep until a specified clock time. This is a wrapper for the C
    clock_nanosleep function.

    Parameters
    ----------
    time_ns : int
        Absolute time (in nanoseconds) as measured by the `clock`.
        clock_nanosleep() suspends the execution of the calling thread until
        this time.
    clock : int, optional
        Clock against which the sleep interval is to be measured, by default
        time.CLOCK_REALTIME. Another option is time.CLOCK_MONOTONIC.

    Returns
    -------
    out : int
        Exit code for the clock_nanosleep function. A non-zero code indicates
        an error.
    """
    deadline_s = time_ns // 1_000_000_000
    deadline_ns = time_ns - (deadline_s * 1_000_000_000)
    deadline = timespec(int(deadline_s), int(deadline_ns))
    out = libc.clock_nanosleep(clock, TIMER_ABSTIME, pointer(deadline), None)
    return out
