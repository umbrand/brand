import signal
import sys
import time
import warnings
from collections import deque

from brand import initializeRedisFromYAML
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
import argparse


warnings.filterwarnings("ignore")

N_SAMPLES = 30000


class Plotter():
    def __init__(self, yaml_path, redis_stream = 'continuousNeural'):
        self.r = initializeRedisFromYAML(yaml_path, 'PLOTTER') # use the new connection function
        self.stream = redis_stream # pick which stream to plot
        self.fig, self.ax = plt.subplots()
        self.xdata = deque([0] * N_SAMPLES, maxlen=N_SAMPLES)
        self.ydata = deque([0] * N_SAMPLES, maxlen=N_SAMPLES)
        self.ln, = plt.plot([], [], '-')
        self.entry_id = '$'
        self.chan = 1
        self.start_time = time.time()
        np.random.seed(int(time.time()))
        signal.signal(signal.SIGINT, self.terminate)

    def init(self):
        #self.ax.set_ylim(-10000, 10000)
        self.ax.set_xlabel('Timestamp (s)')
        self.ax.set_ylabel(self.stream + ' Output')
        return self.ln,

    def update(self, frame):
        entry_list = self.r.xrevrange(self.stream, count=N_SAMPLES)[::-1]
        for entry in entry_list:
            self.entry_id, entry_dict = entry
            y = np.frombuffer(entry_dict[b'samples'], dtype=np.int16).reshape([96,30])
            self.ydata += deque(y[self.chan,:])
            x = np.frombuffer(entry_dict[b'timestamps'], dtype=np.uint32)
            self.xdata += deque(x)
        self.ln.set_data(self.xdata, self.ydata)
        minY,maxY = np.min(self.ydata),np.max(self.ydata)
        self.ax.set_xlim(self.xdata[0], self.xdata[-1])
        self.ax.set_ylim(np.min([self.ax.get_ylim()[0],minY]), np.max([self.ax.get_ylim()[1],maxY]))
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
    description = '''
        Plotting a currently streamed data source.
        '''
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("graphYAML", type=str, help="Path to yaml settings file")
    parser.add_argument("-s","--stream", type=str, help="Redis stream to plot")
    args = parser.parse_args()

    if args.stream is not None: # plot a specific stream if one is named
        plotter = Plotter( yaml_path = args.graphYAML, redis_stream = args.stream)
    else: 
        plotter = Plotter( yaml_path = args.graphYAML)
    
    plotter.run()
