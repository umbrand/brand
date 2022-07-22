# Branded Real-time Asynchronous Neural Data System (BRANDS)
## Architecture
BRANDS is built using a graph architecture with small, individual nodes that can be flexibly interconnected. Each node is a separate process, so as to allow for parallelization and re-prioritization of each node. Interprocess communication and data storage is all built around the [Redis](redis.io) in-memory database and caching system.

The layout of each graph is defined in its associated .yaml settings file. Graph settings files are organized by experimental site to allow easy sharing of graphs between experimental sites while allowing customization per-site. BRANDS is set up to make creation of new graphs and development of new nodes easy and consistent.


## Building
### Requirements
* Host Machine Running Ubuntu 18.04
* Validated on PREEMPT_RT kernel version 5.4.40-rt24
* Nvidia GPU with Compute Capabilities > ?
* CUDA 10.0
* [Anaconda3](https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html) for Linux

### Environment Setup and Make
`bootstrap.sh` is provided to automate the environment setup. It installs debian pkg dependencies using `apt-get` and creates the real-time conda environment (rt), which is defined by `environment.yaml`. [LPCNet](https://github.com/mozilla/LPCNet/),  [hiredis](https://github.com/redis/hiredis), and [redis](https://github.com/antirez/redis/) have been included as submodules, which also get initialized by `bootstrap.sh`. After running bootstrap you simply need to run `make` at the project root. This will build all the project binaries, including submodule dependencies, and output them to `bin/`. Be sure to activate the conda env before running make as Makefiles dependent on cython require it.

```
./boostrap.sh
conda activate rt
make
```

### Adding NI DAQ Support
Download the 2020 version of the installer [here](https://www.ni.com/en-us/support/downloads/drivers/download.ni-linux-device-drivers.html#350003).

1. Install the repository addon:   
`sudo apt install ./<.deb file name>`   
Example:   
`sudo apt install ./ni-software-2020-bionic_20.1.0.49152-0+f0_all.deb`

2. Refresh the package list:   
`sudo apt update`   

3. Use your distribution’s package manager to download and install the driver packages. Package names can be found in the NI Linux Device Drivers readme.
`sudo apt install <package name>`   
Example:   
`sudo apt install ni-daqmx`

4. Update the kernel:   
`sudo dkms autoinstall`

5. Reboot the system.


# Session workflow

Having installed and compiled the code, there are some simple steps needed to run a session. We'll outline the series of instructions needed for running a session, and then describe what each stage is doing.

```
source setup.sh
setSite <site name>
run <graph name>
```

### setup.sh
`source` tells the shell to run all of the commands inside of the .sh file in the current terminal.

`setup.sh` is a script that defines a series of helper functions that make the workflow easier. It also sets the conda environment, in case you forgot. 

### setSite
`setSite` is a helper function defined when you run `setup.sh`. It sets an environmental variable to let BRANDS know where to look for graph YAML settings files. 

`setSite` has tab completion. To see all currently defined sites, type `setSite <TAB> <TAB>`


### run

The `run` command executes the `run.sh` file located in the `run/` directory. It expects a graph name as a command line argument, and has tab completion. To see all currently defined graphs, type `run <TAB> <TAB>`

`run.sh` contains all of the instructions to run an experiment and should not be edited to run a specific graph. Run parses the yaml file from the graph and runs everything accordingly. For a single experiment, it goes through the following steps:

1. Start redis
2. Start the initial nodes 
3. Start the main nodes 
4. Wait until the user types `q <ENTER>`
5. Stop the main nodes
6. Stop the initial nodes
7. Start the finalization nodes 
8. Stop the finalization nodes
9. Save redis database to disk
10. Stop redis

Nodes run in the initial stage should be supportive. For example, these nodes may handle incoming UDP information, replay previously collected data, manage a rest server, etc. The nodes in the main stage do the bulk of the work, including signal processing, decoding algorithms, etc. When the program exits, it first shuts down main and start nodes, and then runs the finalization nodes. For example, nodes that would tidy up the redis database would be called at this stage.



# Folder organization

The primary directory organization within the core BRAND directory is:

```
nodes/
graphs/
lib/
run/
bin/
```

### nodes/
`nodes/` contains all of the code for the different nodes, each separated into a subdirectory. Within each node subdirectory, there should be the original code and a g compatible Makefile if the code is meant to be compiled. The compiled executable should be kept in the same directory and have a .bin extension

### graphs/
`graphs/` contains the YAML settings files for the graphs. The directory organization is:
    
    ```
    graphs/
    |
    --->[graph name]

    ```

### bin/

`bin/` contains the compiled code from non-node supporting functions.

### lib/

lib/ contains a series of libraries or helper functions needed to make the system work. For example:

```
lib/hiredis
lib/redisTools
```

`hiredis` is a submodule that links to a different git repository. `redisTools` is an in-house folder that has some wrapper functions for working with redis.

### run/

This folder should contain all of the information needed to run the session. It will also likely contain the `dump.rdb` file created by redis, and any analysis output pertaining to the run.

## external modules

The core BRAND directory can be extended to run additional graphs and nodes from an external module. From the core BRAND directory, external modules must be installed in the following relative path:  

```
../brand-modules/[module name]/
```

And within each module, the primary organization is the following: 

```
nodes/
graphs/
```

Where `nodes/` and `graphs/` follow the same guidelines as the core BRAND directory. Of note: running `make` within the core directory will also rebuild all nodes within the external module directories.  

## YAML files

### graphs

YAML files used for configuring graphs at minimum should contain information on the Redis connection:
```
RedisConnection:
    redis_realtime_ip: 127.0.0.1
    redis_realtime_port: 6379
    redis_realtime_config: redis.realtime.conf
```
and a list of all nodes to run with their names, version number, execution stage, relative path from core BRAND directory to module, Redis I/O streams, and parameters:
```
Nodes:
    - Name:         node-from-core-brand
      Version:      0.0
      Stage:        start
      module:       .
      redis_inputs:                     [template_stream_A] 
      redis_outputs:                
      Parameters:
            foo:                        42
    - Name:         node-from-external-module
      Version:      0.0
      Stage:        main
      module:       ../brand-modules/some-cool-module
      redis_inputs:                     
      redis_outputs:                    [template_stream_A] 
      Parameters:
            cool-foo:                   42
```

### nodes

YAML files used for configuring nodes can contain whatever sub-headings are needed, but at minimum should contain a key called `parameters` with the following structure:

```
Parameters:
- name: bar
  value: 12345
  description: This text describes how important bar is
  static: true
```

The name of the parameter is called `bar`, and it has value `12345` (N.B. This can be a string or a number). The description is a text-field that describes how the variable is used (and potentially common values). 

Parameters can be "static" or "non-static." A static variable is one that is set during initialization and is not changed thereafter. A non-static is one that can be changed while the module is running. For instance, the host address of the Redis instance will likely be a static, whereas a boolean flag indicating whether a matrix multiplication does or doesn't occur during a node's run-cycle can be static: false. 


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


# Utilities 

## Supervisor 

> Supervisor is a core process in BRAND serving the following functions - 
1. Boots nodes
    - Boots up a single graph with all the nodes and supervisor maintains PIDs of each independently running nodes.
2. Kills nodes
    - Receives command to stop all nodes.
3. Maintain internal model of the state of the graph
    - List of nodes running and their PIDs.
    - Most recent published status of each node.

## Graph/Nodes modules Directory structure
> All internal graphs are required to follow the below mentioned directory structure
```
    |---<nodes>
        |
        |---<nodename>
            |
            |---README.md
            |---src
                |---<Headerfiles>
                |---<nodename>.c
                |---<nodename>.cpp
                |---<nodename>.m
                |---<nodename>.py
            |---<nodename>.bin
            |---<nodename>.out
            |---Makefile 
    |
    |
    |---<graphs>
        |---module_name
            |
            |---<graphname.yaml>
            |---<graphname.pptx>
```


## External modules Directory structure
> All modules are required to follow the below mentioned directory structure

```
---<brand-modules>
    |
    |---<module-name>
        |
        |---<nodes>
            |
            |---<nodename>
                |
                |---README.md
                |---src
                    |---<Headerfiles>
                    |---<module-name>_nodename.c
                    |---<module-name>_nodename.cpp
                    |---<module-name>_nodename.m
                    |---<module-name>_nodename.py
                |---<module-name>_nodename.bin
                |---Makefile   
        |
        |---<graphs>
            |
            |---<graphname.yaml>
            |---<graphname.pptx>
```

## Utilities directory structure
> All utilities used in brand are required to follow the below mentioned directory structure

```
    |---<lib>
    |
    |---<nodes>
            |
            |---<language-utilies(c/python/m/cpp)>
    |---<packages>
            |
            |---<Core packages like hiredis/json which can be used by other modules>
    |---<supervisor_utility>
            |
            |---<README.md>
            |---<requirements.txt>
            |---<supervisor.py> 
```


## Execution of Supervisor
Follow the below instructions and commands for running supervisor utility:

1. Start the supervisor by running either of the following commands:
```    
        $ python3 supervisor/supervisor.py -g <name_of_the_graph_yaml_file>
        $ run -g <name_of_the_graph_yaml_file> 
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


## Redis streams used in supervisor
1. `supergraph_stream` : This stream is used to publish the metadata of the graph.
2. `graph_status` : This stream is used to publish the status of the graph.
3. `supervisor_ipstream` : This stream is used to publish the commands to the supervisor.
4. `<node_name>_stream` : This stream is used for checking data on the <node_name> stream, where <node_name> is the name of the node.
5. `<node_name>_state` : This stream is used to publish the status of the node.

### Graph status codes on `graph_status` stream
> The following are the status codes that are published on `graph_status` stream:
```
    initialized : Graph is initialized.
    parsing : Graph is being parsed for nodes and parameters.
    graph_failed : Graph failed to initialize due to some error.
    running : Graph is parsed and running.
    published : Graph is published on supergraph_stream as a master dictionary.
    stopped/not initialized : Graph is stopped or not initialized.
```
