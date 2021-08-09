# %%
# Message
import asyncio
import os
import time
from dataclasses import field
from typing import Dict, List, Optional, Tuple
from labgraph.graphs.topic import Topic

import matplotlib.animation as animation
import matplotlib.axes
import matplotlib.pyplot as plt
import numpy as np

import labgraph as lg
from utils import RandomMessage

# %%
# Parameters
SAMPLE_RATE = 1e3  # Hz
NUM_FEATURES = 100
WINDOW = 2.0  # seconds
REFRESH_RATE = 2.0  # Hz, how often to update the plot

# %%
# class RandomMessage(lg.Message):
#     timestamp: float
#     data: np.ndarray


# %%
# Steams and Topics
class RollingState(lg.State):
    """State that stores the random messages in a list"""
    messages: List[RandomMessage] = field(default_factory=list)


class RollingConfig(lg.Config):
    """Configuration for the RollingAverager"""
    window: float


class RollingAverager(lg.Node):
    """Node that computes a rolling average on the messages"""
    INPUT = lg.Topic(RandomMessage)
    OUTPUT = lg.Topic(RandomMessage)

    state: RollingState
    config: RollingConfig

    # make this function both a subscriber and a publisher
    @lg.subscriber(INPUT)
    @lg.publisher(OUTPUT)
    async def average(self, message: RandomMessage) -> lg.AsyncPublisher:
        current_time = time.time()
        # append the current message
        self.state.messages.append(message)
        # keep only the messages within the rolling window
        self.state.messages = [
            message for message in self.state.messages
            if message.timestamp >= current_time - self.config.window
        ]
        # if there are no messages, do nothing
        if len(self.state.messages) == 0:
            return
        # take the mean of the messages in numpy
        all_data = np.stack([message.data for message in self.state.messages])
        mean_data = np.mean(all_data, axis=0)
        yield self.OUTPUT, RandomMessage(timestamp=current_time,
                                         data=mean_data)


# %%
# Groups
class GeneratorConfig(lg.Config):
    """Configuration for the Generator node"""
    sample_rate: float
    num_features: int


class Generator(lg.Node):
    """Node that generates random noise"""
    OUTPUT = lg.Topic(RandomMessage)
    config: GeneratorConfig

    @lg.publisher(OUTPUT)
    async def generate_noise(self) -> lg.AsyncPublisher:
        # generate random noise at the given sampling rate
        while True:
            yield self.OUTPUT, RandomMessage(timestamp=time.time(),
                                             data=np.random.rand(
                                                 self.config.num_features))
            await asyncio.sleep(1 / self.config.sample_rate)


class AveragedNoiseConfig(lg.Config):
    """Configuration for the AveragedNoise group"""
    sample_rate: float
    num_features: int
    window: float


class AveragedNoise(lg.Group):
    """Group that generates random noise and outputs a rolling average of it"""
    OUTPUT = lg.Topic(RandomMessage)

    config: AveragedNoiseConfig
    GENERATOR: Generator
    ROLLING_AVERAGER: RollingAverager

    def connections(self) -> lg.Connections:
        group_connections = (
            # connect generator output to averager input
            (self.GENERATOR.OUTPUT, self.ROLLING_AVERAGER.INPUT),
            # connect averager output to group output
            (self.ROLLING_AVERAGER.OUTPUT, self.OUTPUT))
        return group_connections

    def setup(self) -> None:
        # Cascade configuration to contained nodes
        self.GENERATOR.configure(
            GeneratorConfig(sample_rate=self.config.sample_rate,
                            num_features=self.config.num_features))
        self.ROLLING_AVERAGER.configure(
            RollingConfig(window=self.config.window))


# %%
# Plot
class PlotState(lg.State):
    """Data for the plot. Contains a NumPy array of matplotlib axes or None."""
    data: Optional[np.ndarray] = None


class PlotConfig(lg.Config):
    refresh_rate: float
    num_bars: int


class Plot(lg.Node):
    INPUT = lg.Topic(RandomMessage)
    state: PlotState
    config: PlotConfig

    def setup(self) -> None:
        """Initialize self.ax to None"""
        self.ax: Optional[matplotlib.axes.Axes] = None

    @lg.subscriber(INPUT)
    def got_message(self, message: RandomMessage) -> None:
        """Receive data and update the node's state."""
        self.state.data = message.data

    @lg.main
    def run_plot(self) -> None:
        """Plot data"""
        fig = plt.figure()
        self.ax = fig.add_subplot(1, 1, 1)
        self.ax.set_ylim([0, 1])
        anim = animation.FuncAnimation(fig,
                                       self._animate,
                                       interval=1 / self.config.refresh_rate *
                                       1000)
        plt.show()
        raise lg.NormalTermination()

    def _animate(self, i: int) -> None:
        if self.ax is None:
            return
        self.ax.clear()
        self.ax.set_ylim([0, 1])
        self.ax.bar(range(self.config.num_bars), self.state.data)
        self.ax.set_xlabel('Features')
        self.ax.set_ylabel('Rolling Average')


# %%
# Logging
# help(lg.LoggerConfig)

# %%
lg.LoggerConfig(output_directory=os.getcwd(), streams_by_logging_id={})


# %%
# Groups
class Demo(lg.Graph):
    AVERAGED_NOISE: AveragedNoise
    PLOT: Plot

    def setup(self) -> None:
        self.AVERAGED_NOISE.configure(
            AveragedNoiseConfig(sample_rate=SAMPLE_RATE,
                                num_features=NUM_FEATURES,
                                window=WINDOW))
        self.PLOT.configure(
            PlotConfig(refresh_rate=REFRESH_RATE, num_bars=NUM_FEATURES))

    def connections(self) -> lg.Connections:
        return ((self.AVERAGED_NOISE.OUTPUT, self.PLOT.INPUT), )

    def process_modules(self) -> Tuple[lg.Module, ...]:
        return (self.AVERAGED_NOISE,)

    def logging(self) -> Dict[str, Topic]:
        return {
            'noise_input': self.AVERAGED_NOISE.GENERATOR.OUTPUT,
            'noise_avg': self.AVERAGED_NOISE.OUTPUT
        }


# %%
if __name__ == "__main__":
    # initialize and configure the graph
    config_type = Demo.__config_type__
    config = config_type.fromargs()
    graph = Demo()
    graph.configure(config)

    # configure the logger
    logger_config = lg.LoggerConfig(output_directory=os.getcwd(),
                                    recording_name='simple_viz_no_plot')

    # run the graph
    runner = lg.ParallelRunner(
        graph=graph, options=lg.RunnerOptions(logger_config=logger_config))
    runner.run()
# %%
