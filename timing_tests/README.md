# BRANDS Timing Tests
This Folder contains timing tests used to measure latencies of graphs using the BRANDS system.
## Test Structure
#### There are two types of tests:
* Publisher nodes are run continously using a `while True:` loop
    * Found in `chrt_while_1` folder
* Publisher nodes are allowed to sleep using a `clock_nanosleep` python wrapper
    * Found in `chrt_nanosleep` folder

#### Four different graphs are included within each test type folder:
* Vanilla Publisher to Vanilla Subscriber
* Function Generator to OLE Decoder
* Function Generator to RNN Decoder
* Function Generator to Neural Data Transformer (NDT) Decoder

#### Each graph produces a plot (found in the `plots` folder of the respective test) measuring 3 different latencies:
* The Intersample Latency of the Publisher nodes (How frequently samples are produced)
* The transmission/redis latency between the two nodes
* The Decoder/Subscriber node latency

The dataframe used to produce these plots is saved as a pickle file found in the `dataframes` folder of the respective graph.

**NOTE: We have included Baseline test plots that can be found in each test's `plots` folder.**

## How to Run the Timing Tests
#### Running the timing tests requires two things:
* Starting a supervisor instance
* Traveling to the desired graph's directory and running the timing script

**NOTE: All baseline tests were run using cpu affinity, unix sockets, and realtime priority**

#### Here's an example: <br>
Say we want to run a timing test using the OLE decoder and nanosleep loop, you would do the folowing things:
1. Start a supervisor instance, specifying the appropriate parameters (**the parameters below show the supervisor parameters used for the baseline tests**)
>`supervisor -r 99 -s /var/run/redis.sock -a 0-3`
2. In a seperate terminal, travel to the following directory
>`realtime_rig_dev/timing_tests/chrt_nanosleep/OLE` <br>

    and run the timing test script:
>`./ole_timing.py`
