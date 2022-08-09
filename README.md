# BRAND Real-time Asynchronous Neural Data System (BRAND)

## Overview
BRAND is built using a graph architecture with small, individual nodes that can be flexibly interconnected. Each node is a separate process, so as to allow for parallelization and re-prioritization of each node. Interprocess communication and data storage is all built around the [Redis](redis.io) in-memory database and caching system.

The layout of each graph is defined in its associated .yaml configuration file. Graph configuration files are organized by experimental site within modules, to allow easy sharing of graphs between experimental sites while allowing per-site customization. BRAND is set up to make creation of new graphs and development of new nodes easy and consistent.

## Installation

### Requirements
* Host Machine Running Ubuntu 18.04
* Validated on PREEMPT_RT kernel version 5.4.40-rt24
* [Anaconda3](https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html) for Linux

### Environment setup and Make
`bootstrap.sh` is provided to automate the environment setup. It installs debian pkg dependencies using `apt-get` and creates the real-time conda environment (rt), which is defined by `environment.yaml`. [LPCNet](https://github.com/mozilla/LPCNet/),  [hiredis](https://github.com/redis/hiredis), and [redis](https://github.com/antirez/redis/) have been included as submodules, which also get initialized by `bootstrap.sh`. After running bootstrap you simply need to run `make` at the project root. This will build all the project binaries including submodule dependencies. Be sure to activate the conda env before running make as Makefiles dependent on cython require it.

```
./boostrap.sh
conda activate rt
make
```

Of note: if any of the source code is updated (for example, when developing a new node), `make` needs to be re-run for those changes to be reflected in the binaries that are run by BRAND. 

## Directory structure

BRAND follows the following directory structure (where `brand` corresponds to the main folder for this repository):

```
|---brand
    |---nodes
    |---graphs
    |---lib
        |---c
        |---python
        |---<packages>
    |---supervisor
|---brand-modules
    |---<module-name>
        |---nodes
        |---graphs
```
where `<module-name>` is the name of the name of an external code module that extends the core BRAND code through its own nodes and graphs (details on this below). 

### nodes/
The `nodes` folder contains the code for different nodes that implement specific modular functions, each separated into its own subdirectory. Within each node subdirectory, there should be the node's source code (can be optionally organized within a `src` directory), a gnu-compatible Makefile for compiling the source code and generating the node's binary executable, and a README. Running `make` from the main BRAND directory, goes thorugh all of the node subdirectories and runs the respective Makefile, which should generate the compiled executable within the same directory and have a `.bin` extension. Ensure that you follow the below directory structure for each node:

```
|---nodes
    |---<node_name>
        |---<src_code>
        |---Makefile 
        |---README.md
        |---<node_name>.bin (built after running make)
```

### graphs/
The `graphs` folder contains the YAML configuration files for the graphs. This directory's organization is:

```
|---graphs
    |---<graph_name>
        |---<graph_name.yaml>
```

### lib/

The `lib` folder contains libraries and helper functions required for the system to work. This includes BRAND specific C or Python libraries (c and python folders) and external packages (e.g. redis and hiredis). This directory's organization is:

```
|---lib
    |---c
    |---python
    |---redis
    |---hiredis
    |---<package_name>
```

### supervisor/

This folder contains the code for the `supervisor` process, which is a core process in BRAND serving the following functions:
1. Start a Redis server
2. Load a graph and start nodes (upon receiving a "start" command)
3. Maintain an internal model with the state of the graph
    - List of nodes running and their PIDs
    - Most recent published status of each node
4. Stop graph and nodes (upon receiving a "stop" command)

### brand-modules/

The core BRAND directory can be extended to run additional graphs and nodes from external modules. From the core BRAND directory, external modules must be installed to a `module-name` folder at the following path relative the to main BRAND directory:  

```
../brand-modules/<module-name>/
```

Within each module, the directory structure is the following: 

```
|---<module-name>
    |---nodes
    |---graphs
```

Where `nodes/` and `graphs/` follow the same guidelines as the core BRAND directory. Of note: running `make` within the core directory will also go through the node Makefiles and rebuild the binary executables within all external module directories.  

## Graph YAML files

The configuration for a graph, that is, which nodes to run and using which parameters, is specified thorugh a graph YAML file. At a minimum, a graph YAML file should include a list of all nodes to run with their names, (unique) nicknames, relative path from core BRAND directory to module directory, and parameter list. Optionally, the graph YAML can also include the run priority for nodes and ID of the machine on which to run the node.
```
nodes:
  - name: <node1_name>
    nickname: <unique_nickname>
    module: <path_to_module>
    run_priority (optional): <run_priority>
    machine: <machine_id>   
    parameters:
      <parameter1_name>: <parameter1_value>
      <parameter2_name>: <parameter2_value>
      ...
  - name: <node2_name>
    nickname: <unique_nickname>
    module: <path_to_module>
    run_priority: <run_priority>
    machine: <machine_id>   
    parameters:
      <parameter1_name>: <parameter1_value>
      <parameter2_name>: <parameter2_value>
      ...
  ...
```

## Session workflow

After having installed and compiled the node executables, the following commands must be run to start the BRAND system:

```
$ source setup.sh
$ supervisor [args]
```

 - `setup.sh` is a script that defines a series of helper functions that make the workflow easier. It also sets the conda environment. 
 - `supervisor` is the core process controlling the BRAND system

### Using the `supervisor`

1. Start the `supervisor` process by running either of the following commands:
```    
$ supervisor [args]
```
Optionally, you can include extra arguments when running the `supervisor` to override its defaults. Below are the extra arguments that can be used:
 
 - `-i` / `--ip`: IP address to bind the server node to (default: 127.0.0.1)
 - `-p` / `--port`: Port number to bind the server node to (default: 6379)
 - `-c`/ `--cfg`: Path to the Redis config file used to start the server (default: `supervisor/redis.supervisor.conf`)
 - `-m` / `--machine`: ID of the machine on which the supervisor is running (default: none)
 - `-g` / `--graph`: Name of the graph YAML file to pre-load (default: none)
Example usage:
```    
$ supervisor -i 192.168.0.101 --port 6379
```

2. Once the `supervisor` is running, it must receive a `startGraph` command through Redis to its `supervisor_ipstream` to start a graph. An example way to do this (which we suggest for testing) is to use `redis-cli`. You would have to open a separate terminal and first run the following command to open `redis-cli` (-h and -p flags are optional if you're running on default host/IP and port):
```
    $ redis-cli -h <host> -p <port>
```
And you can then send the `startGraph`, providing the path to the graph YAML file to run: 
```
    $ XADD supervisor_ipstream * commands startGraph file <path_to_the_graph_yaml_file>
```
The `supervisor` will log a series of outputs following this command as it goes thorugh the graph YAML file, checks for node executable binaries and starts the nodes. All nodes from the graph YAML will be running after this.

3. To stop the graph, use the following Redis command (using `redis-cli` or other Redis interface):
```
    $ XADD supervisor_ipstream * commands stopGraph
```
Alternatively to stop the graph and save NWB export files, use the following Redis command (using `redis-cli` or other Redis interface). Note that this will require having your graph and nodes set up to support the [NWB Export Guidelines](https://github.com/snel-repo/realtime_rig_dev/blob/dev/doc/ExportNwbGuidelines.md).
```
    $ XADD supervisor_ipstream * commands stopGraphAndSaveNWB 
```

### Supported `supervisor` commands

Commands can be sent to the `supervisor` through Redis using the following syntax: `XADD supervisor_ipstream * commands <command_name> [<arg_key> <arg_value>]`. The following commands are currently implemented:

* `startGraph` [file <path_to_file>]: Start graph from YAML file path.
* `stopGraph`: Stop graph, by stopping the processes for each running node.
* `stopGraphAndSaveNWB`: Stop graph, save `rdb` file, generate NWB file, and flush the Redis database. Requires following the following guidelines: [NWB Export Guidelines](https://github.com/snel-repo/realtime_rig_dev/blob/dev/doc/ExportNwbGuidelines.md). Suggested for running independent session blocks.

### Redis streams used with the `supervisor`
### Multi-machine graphs
BRAND is capable of running nodes on several machines using the same graph. To run multi-machine graphs, you must start a `supervisor` process on the host machine that will contain your `redis-server` and a `booter` process on every client machine that will be involved in node execution.

* `supervisor_ipstream`: This stream is used to publish commands for the supervisor.
* `graph_status`: This stream is used to publish the status of the current graph.
* `supergraph_stream`: This stream is used to publish the metadata of the graph.
* `<node_name>_state`: This set of streams are used to publish the status of nodes.
* `<data_stream>`: These are arbitrary data streams through which nodes publish their data to Redis. There are currently no rules as to how many data streams a node can publish to or naming conventions for these streams. 
`booter` is similar to `supervisor` except it does not start its own `redis-server`. Here are its command-line arguments:
```
usage: booter [-h] -m MACHINE [-i HOST] [-p PORT] [-l LOG_LEVEL]

optional arguments:
  -h, --help            show this help message and exit
  -m MACHINE, --machine MACHINE
                        machine on which this booter is running
  -i HOST, --host HOST  ip address of the redis server (default: 127.0.0.1)
  -p PORT, --port PORT  port of the redis server (default: 6379)
  -l LOG_LEVEL, --log-level LOG_LEVEL
                        Configure the logging level
```
To support multi-machine graphs, use the `--machine` (or `-m`) flag to assign a name for each machine when starting `supervisor` or `booter`. When `--machine` is given, `supervisor` only runs the nodes that specify the same `machine` in the graph YAML. For compatibility with single-machine graphs, `supervisor` also runs all nodes that do not provide a `machine` name in the graph YAML.
The above streams can be checked using Redis stream commands (e.g. `XREVRANGE`, `XREAD`). For example, to check the current graph published in the form of a master dictionary, you can use the following Redis command (using `redis-cli` or other Redis interface):
```
    $ XREVRANGE supergraph_stream + - COUNT 1
```

### Checking a graph's status
Here's an example YAML entry for a node that will run on a machine named "brand":
```yaml
nodes:
    - name:         func_generator
      version:      0.0
      nickname:     func_generator
      stage:        main
      module:       .
      machine:      brand  # this node will run on the machine named 'brand'
      run_priority:                 99
      parameters:
                sample_rate:        1000
                n_features:         96
                n_targets:          2
                log:                INFO 
```The following are the status codes that are published on the `graph_status` stream:
* `initialized`: Graph is initialized.
* `parsing`: Graph is being parsed for nodes and parameters.
* `graph failed`: Graph failed to initialize due to some error.
* `running`: Graph is parsed and running.
* `published`: Graph is published on supergraph_stream as a master dictionary.
* `stopped/not initialized`: Graph is stopped or not initialized.

You can check the status of the graph using the following Redis command (using `redis-cli` or other Redis interface):
```
    $ XREVRANGE graph_status + - COUNT 1
```How to run a multi-machine graph (e.g. [testBooter.yaml](./graphs/testGraph/testBooter.yaml)):
1. Run `source setup.sh` to load the new `supervisor` and `booter` aliases
2. Start `supervisor`. In this example, the host machine's local IP address is `192.168.1.101`.
```bash
supervisor -m brand -i 192.168.1.101
```
3. Then, log into each client machine, and start a `booter` process, using a unique name for each machine. We will use one client machine called "gpc":
```bash
booter -m gpc -i 192.168.1.101  # name this machine 'gpc'
```
4. Enter the `redis-cli`:
```
redis-cli -h 192.168.1.101
```
5. Start a graph (in the `redis-cli`):
```
XADD supervisor_ipstream * commands startGraph file graphs/testGraph/testBooter.yaml
```
6. Stop the graph (in the `redis-cli`):
```
XADD supervisor_ipstream * commands stopGraph
```
If everything is working correctly, you should see that the `func_generator` node ran on the "brand" machine, and the `decoder` node ran on the "gpc" machine.


## Redis as a mechanism for IPC

The primary mode of inter-process communication with BRAND is using Redis, focusing on [Redis streams](https://redis.io/topics/streams-intro). Briefly, Redis is an in-memory cache key-based database entry. It solves the problem of having to rapidly create, manipulate, and distribute data in memory very quickly and efficiently. 

A stream within redis has the following organization:

```
stream_key ID key value key value ...
```


The `ID` defaults to the millisecond timestamp of when the piece of information was collected. It has the form `MMMMMMMMM-N`, where N is a number >= 0. The idea is that if there are two entries at the same millisecond timestep, they can be uniquely identified with the N value. N begins at N and increments for every simultaneously created entry within the same millisecond.

When a node wants to share data with others, it does so using a stream. There are several advantages to using a stream: 

1. Data is automatically timestamped
2. Adding new data to the stream is cheap, since it's stored internally as a linked-list. 
3. It makes it easy to have a pub/sub approach to IPC, since nodes can simply call the `xread` command 
4. It makes it easy to query previously collected data using the `xrange` or `xrevrange` command. Reading new data from either the head or the tail of the stream is computationally cheap.

## Creating a new node

Nodes can be written in any language. Nodes are launched, and stopped, in the `run.sh` script. Conceptually, a node should [do one thing and do it well](https://en.wikipedia.org/wiki/Unix_philosophy). Nodes are designed to be chained together in sequence. It should not be surprising if an experimental session applying real-time decoding to neural data would have on the order of 6-12 nodes running.

At a minimum, a node should have the following characteristics:

1. Be associated with a binary executable that parses the following command-line flags in order for a successful execution from the `supervisor`:
    * `s`: Redis socket to bind node to.
    * `n`: Nickname of the node.
    * `i`: Redis server host name or IP address to bind node to .
    * `p`: Redis server port to bind node to.

A node will prioritize the socket flag over the host/port flags. Execution of a node should fail is neither `i`/`p` or `s` flags are provided.

2. Load its parameters by reading from a well-known stream that contains a master JSON of the graph (`supergraph_stream`).
3. Have a concept of "state", which is communicated through Redis (`<node_name>_state` stream).
4. Catch SIGINT to close gracefully.

If developing a node in Python, we suggest to implement it as a class that inherits from the `BRANDNode` class within the installed `brand` library, since it already implements the above. 

## Performance Optimization

CPUs will scale their operating frequency according to load, which makes it difficult to get predictable timing. To get around this, we'll use `cpufrequtils`:
```
sudo apt install cpufrequtils
sudo systemctl disable ondemand
sudo systemctl enable cpufrequtils
```

Setting the CPU at its maximum allowable frequency (which will still be reduced if the CPU gets too hot):
```
sudo cpufreq-set -g performance
```

Renabling CPU scaling to save power:
```
sudo cpufreq-set -g powersave
```

This was tested on Intel CPUs. The commands may be difference for CPUs from other manufacturers.

## Gotchas

### PREEMPT_RT kernel bash fork error.

It turns out that with Ubuntu 18.04 running PREEMPT_RT kernel version 5.4.40-rt24, there are some surprising conditions under which the terminal will crash, resulting in a `bash: fork: error` being displayed in the terminal, requiring one to restart their connection.

First, *do not write a node that both sets a `SCHED_FIFO` prioritization and interacts with Redis*. The way around this is to have a process do one or the other. If a process needs to run a timer, then have the process `pause()` until if gets a signal from a different node (scheduled with SCHED_FIFO) indicating that it's time to run.

Second, *do not write a node that sets `SCHED_FIFO` that is launched from python*. The way to do this is to lanch the processes using the `run.sh` script. 

### Saving data in Redis with minimal latency

By default, Redis is configured to periodically [save](https://redis.io/topics/persistence). Given that BRAND can be processing a great deal of information quickly, the background save procedures will result in significant latencies in real-time decoding.

One option is to simply remove the `save` configuration parameters in the `.conf` file. However, if Redis is terminated using SIGTERM or SIGINT, then the [default behavior of writing to disk](https://redis.io/topics/signals) does not occur. To get around this, write something like `save NNN 1` in the configuration file, where NNN is a number much bigger than how long you ever expect to run your session. This way, Redis will gracefully exit and save your data to disk.

### hiredis library

[hiredis](https://github.com/redis/hiredis) is a C library for interacting with Redis. It is excellent, but it has undocumented behavior when working with streams. Calling `xrange` or `xrevrange` will result in a `REDIS_REPLY_ARRAY`, regardless of whether the stream exists or not. Moreover, `reply->len` will always be 0, despite possibly having many returned entries. The way around this is to first call the redis command `exists`.

### Alarms and reading from file

If a process is reading from a file descriptor and an alarm goes off, there can be unforunate consequence. For instance, if SIGALRM goes off while python is reading a file, reading will be interrupted and downstream processes can crash. If a process is setting an alarm, be sure to start it right before entering its main loop (and after the handlers have been installed), after all of the relevant configuration has been set.

### Running a script with sudo privileges within the current conda environment
```
sudo -E env "PATH=$PATH" ./myscript
```

### Removing headers from UDP packet capture
Dependencies: [tshark](https://packages.ubuntu.com/bionic/tshark), [bittwist](https://packages.ubuntu.com/bionic/bittwist)   

If you have `.pcapng` files, convert them to `.pcap`:
```
tshark -F pcap -r mypackets.pcapng -w mypackets.pcap
```
Use Wireshark to check the size of the header. In our case, the header is the first 42 bytes in each packet, so we run:
```
bittwiste -I mypackets.pcap -O mypackets_no_headers.pcap -D 1-42
```
Now `mypackets_no_headers.pcap` is a copy of our `mypackets.pcap` file with headers removed.




