import labgraph as lg
import numpy as np


class RandomMessage(lg.Message):
    timestamp: float
    data: np.ndarray
