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

#### Each Decoder graph produces a plot (found in the `plots` folder of the respective test) measuring 3 different latencies:
* The Intersample Latency of the Function Generator node (How frequently samples are produced)
* The transmission/redis latency between the two nodes
* The Decoder/Subscriber node latency

#### The Vanilla Pub/Sub graph produces a plot showing 2 different latencies:
* The Intersample Latency of the Publisher node (How frequently samples are produced)
* The transmission/redis latency between the Publisher and Subscriber nodes

**Each of these latencies is shown vs time and as a histogram**

The dataframe used to produce these plots is saved as a pickle file found in the `dataframes` folder that is created after running the respective graph.

**NOTE: We have included Baseline test plots that can be found in each test's `plots` folder.**

## How to Run the Timing Tests
#### Running the timing tests requires two things:
* Starting a supervisor instance
* Traveling to the desired graph's directory and running the timing script

**NOTE: All baseline tests were run using cpu affinity, unix sockets, and realtime priority**

#### Here's an example: <br>
Say we want to run a timing test using the OLE decoder and nanosleep loop, you would do the folowing things:
1. Start a supervisor instance, specifying the appropriate parameters (**the parameters below show the supervisor parameters used for the baseline tests**)
```
supervisor -r 99 -s /var/run/redis.sock -a 0-3
```
2. In a seperate terminal, travel to the following directory
```
realtime_rig_dev/timing_tests/chrt_nanosleep/OLE
```

3. Run the timing test script:
```
python ole_timing_test.py
```

To run all tests at once (OLE, RNN, NDT, PubSub) use the bash script from either the `chrt_nanosleep` or the `chrt_while_1` folder:
```
bash run_analyses.sh
```

**Note: To change the number of channels used for graphs including the RNN or NDT nodes, you must change the graph parameters in the timing scripts AND the decoder parameter yaml file of the node. The RNN config can be found at `nodes/RNN_decoder/src/train_RNN.yaml` and the NDT config can be found at `nodes/ndt/src/config.yaml`.**
