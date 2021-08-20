import signal
import sys
from collections import deque

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from redis import Redis
import time
import warnings

warnings.filterwarnings("ignore")

N_SAMPLES = 100


class Plotter():
    def __init__(self):
        self.r = Redis(host='127.0.0.1', port=6379)
        self.fig, self.ax = plt.subplots()
        self.xdata = deque([0] * N_SAMPLES, maxlen=N_SAMPLES)
        self.ydata = deque([0] * N_SAMPLES, maxlen=N_SAMPLES)
        self.ln, = plt.plot([], [], 'o-')
        self.entry_id = '$'
        self.start_time = time.time()
        signal.signal(signal.SIGINT, self.terminate)

    def init(self):
        self.ax.set_ylim(-100, 100)
        self.ax.set_xlabel('Timestamp (s)')
        self.ax.set_ylabel('Decoder Output')
        return self.ln,

    def update(self, frame):
        entry_list = self.r.xrevrange('decoder', count=N_SAMPLES)[::-1]
        for entry in entry_list:
            self.entry_id, entry_dict = entry
            y = np.frombuffer(entry_dict[b'y'], dtype=np.float64)
            self.ydata.append(float(y))
            self.xdata.append(float(entry_dict[b'ts']))
        self.ln.set_data(self.xdata, self.ydata)
        self.ax.set_xlim(self.xdata[0], self.xdata[-1])
        self.ax.figure.canvas.draw_idle()
        return self.ln,

    def run(self):
        self.anim = FuncAnimation(self.fig,
                                  self.update,
                                  init_func=self.init,
                                  repeat_delay=int(1e3 / 60))
        plt.show()

    def terminate(self, sig, frame):
        sys.exit(0)


if __name__ == "__main__":
    plotter = Plotter()
    plotter.run()
