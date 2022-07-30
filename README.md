# BRAND Real-time Asynchronous Neural Data System (BRAND)

## Overview
BRAND is built using a graph architecture with small, individual nodes that can be flexibly interconnected. Each node is a separate process, so as to allow for parallelization and re-prioritization of each node. Interprocess communication and data storage is all built around the [Redis](redis.io) in-memory database and caching system.

The layout of each graph is defined in its associated .yaml configuration file. Graph configuration files are organized by experimental site within modules, to allow easy sharing of graphs between experimental sites while allowing per-site customization. BRAND is set up to make creation of new graphs and development of new nodes easy and consistent.

## Installation

### Requirements
* Host Machine Running Ubuntu 18.04
* Validated on PREEMPT_RT kernel version 5.4.40-rt24
* Nvidia GPU with Compute Capabilities > ?
* CUDA 10.0
* [Anaconda3](https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html) for Linux

### Environment Setup and Make
`bootstrap.sh` is provided to automate the environment setup. It installs debian pkg dependencies using `apt-get` and creates the real-time conda environment (rt), which is defined by `environment.yaml`. [LPCNet](https://github.com/mozilla/LPCNet/),  [hiredis](https://github.com/redis/hiredis), and [redis](https://github.com/antirez/redis/) have been included as submodules, which also get initialized by `bootstrap.sh`. After running bootstrap you simply need to run `make` at the project root. This will build all the project binaries including submodule dependencies. Be sure to activate the conda env before running make as Makefiles dependent on cython require it.

```
./boostrap.sh
conda activate rt
make
```

Of note: if any of the source code is updated (for example, when developing a new node), `make` needs to be re-run for those changes to be reflected in the binaries that are run by BRAND. 

## Directory Structure

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

## Execution of Supervisor
Follow the below instructions and commands for running supervisor utility:

1. Start the supervisor by running either of the following commands:
```    
    $ supervisor
    $ python3 supervisor/supervisor.py -g <name_of_the_graph_yaml_file>
```
 >Optionally, you can also use extra arguments with the supervisor utility. Below are the extra arguments that can be used:
 - `-g` / `--graph` : Name of the graph yaml file.
 - `-i` / `--ip` : IP address to bind the server node to.
 - `-p` / `--port` : Port number to bind the server node to.
 - `-c`/ `--cfg` : Name of the config file specific to redis server.
 - `-m` / `--machine` : Name of the machine on which the supervisor is running.


2. Once, the supervisor has started, you can open a separate terminal and run the following commands (-h and -p flags are optional if you're running on default host and port):
```
    $ redis-cli -h <hostname> -p <port>
```
3. Inside the redis-cli, run the following commands to start the graph:
```
    $ XADD supervisor_ipstream * commands startGraph
```
4. (Optional) If you want to start the graph with a specific file, run the following command:
```
    $ XADD supervisor_ipstream * commands startGraph file       <name_of_the_graph_yaml_file>
```    
5. Now that the nodes have started, you can check the status of the graph using the following command in redis-cli:
```
    $ XREVRANGE graph_status + - COUNT 1
```

6. To check the metadata published in form of a master dictionary, run the following command in redis-cli:
```
    $ XREVRANGE supergraph_stream + - COUNT 1
```
7. To stop the graph, run the following command in redis-cli:
```
    $ XADD supervisor_ipstream * commands stopGraph
```
8. To stop the graph and save NWB export files, run the following command in redis-cli:
```
    $ XADD supervisor_ipstream * commands stopGraphAndSaveNWB
```


### Redis streams used in supervisor
1. `supergraph_stream` : This stream is used to publish the metadata of the graph.
2. `graph_status` : This stream is used to publish the status of the graph.
3. `supervisor_ipstream` : This stream is used to publish the commands to the supervisor.
4. `<node_name>_stream` : This stream is used for checking data on the <node_name> stream, where <node_name> is the name of the node.
5. `<node_name>_state` : This stream is used to publish the status of the node.

### Graph status codes on `graph_status` stream
> The following are the status codes that are published on `graph_status` stream:
```
    initialized             - Graph is initialized.
    parsing                 - Graph is being parsed for nodes and parameters.
    graph_failed            - Graph failed to initialize due to some error.
    running                 - Graph is parsed and running.
    published               - Graph is published on supergraph_stream as a master dictionary.
    stopped/not initialized - Graph is stopped or not initialized.
```




## Session workflow

Having installed and compiled the code, there are some simple steps needed to run a session. We'll outline the series of instructions needed for running a session, and then describe what each stage is doing.

```
source setup.sh
setSite <site name>
run <graph name>
```

### setup.sh
`source` tells the shell to run all of the commands inside of the .sh file in the current terminal.

`setup.sh` is a script that defines a series of helper functions that make the workflow easier. It also sets the conda environment, in case you forgot. 






## Redis as a mechanism for IPC

The primary mode of inter-process communication with RANDS is using Redis, focusing on [Redis streams](https://redis.io/topics/streams-intro). Briefly, Redis is an in-memory cache key-based database entry. It solves the problem of having to rapidly create, manipulate, and distribute data in memory very quickly and efficiently. 

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

# Creating a new node

Nodes can be written in any language. Nodes are launched, and stopped, in the `run.sh` script. Conceptually, a node should [do one thing and do it well](https://en.wikipedia.org/wiki/Unix_philosophy). Nodes are designed to be chained together in sequence. It should not be surprising if an experimental session applying real-time decoding to neural data would have on the order of 6-12 nodes running.

At a minimum, a node should have the following characteristics:

1. Catch SIGINT to close gracefully
2. Have a `.yaml` configuration file

Since it's inpredictable how nodes will be stopped during a session, it's important to have graceful process termination in the event of a SIGINT being sent to the process. This is especially important because if processes are initiated using `run.sh`, the SIGINT sent to the bash script will be propagated to the node.

# Performance Optimization
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

# Gotchas

### PREEMPT_RT kernel bash fork error.

It turns out that with Ubuntu 18.04 running PREEMPT_RT kernel version 5.4.40-rt24, there are some surprising conditions under which the terminal will crash, resulting in a `bash: fork: error` being displayed in the terminal, requiring one to restart their connection.

First, *do not write a node that both sets a `SCHED_FIFO` prioritization and interacts with Redis*. The way around this is to have a process do one or the other. If a process needs to run a timer, then have the process `pause()` until if gets a signal from a different node (scheduled with SCHED_FIFO) indicating that it's time to run.

Second, *do not write a node that sets `SCHED_FIFO` that is launched from python*. The way to do this is to lanch the processes using the `run.sh` script. 

### Saving data in Redis with minimal latency

By default, Redis is configured to periodically [save](https://redis.io/topics/persistence). Given that RANDS can be processing a great deal of information quickly, the background save procedures will result in significant latencies in real-time decoding.

One option is to simply remove the `save` configuration parameters in the `.conf` file. However, if Redis is terminated using SIGTERM or SIGINT, then the [default behavior of writing to disk](https://redis.io/topics/signals) does not occur. To get around this, write something like `save NNN 1` in the configuration file, where NNN is a number much bigger than how long you ever expect to run your session. This way, Redis will gracefully exit and save your data to disk.

### hiredis library

[hiredis](https://github.com/redis/hiredis) is a C library for interacting with Redis. It is excellent, but it has undocumented behavior when working with streams. Calling `xrange` or `xrevrange` will result in a `REDIS_REPLY_ARRAY`, regardless of whether the stream exists or not. Moreover, `reply->len` will always be 0, despite possibly having many returned entries. The way around this is to first call the redis command `exists`.

### Alarms and reading from file

If a process is reading from a file descriptor and an alarm goes off, there can be unforunate consequence. For instance, if SIGALRM goes off while python is reading a file, reading will be interrupted and downstream processes can crash. If a process is setting an alarm, be sure to start it right before entering its main loop (and after the handlers have been installed), after all of the relevant configuration has been set.

### Permission denied for a scripts
```
$ load cerebrusTest
bash: ./session/cerebrusTest/load.sh: Permission denied
```
If you see this error, run `chmod +x ./session/cerebrusTest/load.sh` to make the script executable.


### `run` command does not execute the `run.sh` script corresponding to the loaded session
This can happen if a `run/` folder already exists prior to running `load mysession`. The `load.sh` script in each session is usually designed to not overwrite an existing `run/` folder. If a run folder exists already you will need to move it before a new session can be loaded.


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




