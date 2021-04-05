# Real-time Asynchronous Neural Decoding System (RANDS)
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
load cerebusTest
run
```

`setup.sh` is a script that defines a series of helper functions that make the workflow easier. It also sets the conda environment, in case you forgot. 

### load.sh

The `load cerebusTest` command executes the `load.sh` in the folder `session/cerebusTest`. The `load.sh` file contains all of the configuration information required in order to start an experiment. At the end of calling `load.sh`, all files pertaining to an experiment will be put into the folder `run/`. At a minimum, after calling `load.sh` there should be a file `run/run.sh`.

Examples of the contents for a `session/` folder include the `yaml` files used for configuring modules, `.conf` files for configuring redis, etc. This makes it easy to keep all of the information in one place. Usually the process of populating a `run/` folder is done with symbolic links. For instance, `load.sh` will create symbolic links to binaries in the `bin/`, such as linking `bin/cerebusAdapter` to `run/cerebusAdapter`. Next, it will create a symbolic link from `proc/rest/rest.pyx` to `run/rest.pyx`. By looking at the list of links, one should know exactly what modules are called, and where they're defined. 

The expectation is that multiple session types will use a combination of different modules to run an experiment. However, the configurations for each module may be different depending on the experiment being performed. 


### run.sh

The `run` command executes the `run.sh` file located in the `run/` directory. `run.sh` should contain the instructions to run an experiment. Running an experiment has the following sequences of events:

1. Start redis
2. Start the initial modules 
3. Start the main modules 
4. Wait
5. Stop the main modules
6. Stop the initial modules
7. Start the finalization modules 
8. Stop the finalization modules
9. Save redis database to disk
10. Stop redis

Modules run in the initial stage should be supportive. For example, these modules may handle incoming UDP information, replay previously collected data, manage a rest server, etc. The modules in the main stage do the bulk of the work, including signal processing, decoding algorithms, etc. When the program exits, it first shuts down main and start modules, and then runs the finalization modules. For example, modules that would tidy up the redis database would be called at this stage.



# Folder organization

The primary organization of the rig is:

```
bin/
lib/
proc/
session/
run/
```

### bin/

`bin/` contains the compiled output of the various processes. Calling `make` in the root directory will make all of the modules and git submodules (e.g. redis, etc.). To compile a specific process, run `make [process]` from the root directory.

### lib/

lib/ contains a series of libraries or helper functions needed to make the system work. For example:

```
lib/hiredis
lib/redisTools
```

`hiredis` is a submodule that links to a different git repository. `redisTools` is an in-house folder that has some wrapper functions for working with redis.

### proc/

The `proc/` folder contains the modules used for the rig. Suppose we call our module `foo`. If `foo` is written in a compiled language, like C, then it should have as a minimum:

```
proc/foo/foo.c
proc/foo/foo.yaml
proc/foo/README.md
proc/foo/Makefile
```

If processes need to be compiled: they should be written so that they are compiled in their local directory (i.e. `/proc/foo/`), with the destination of the binary being the `bin/` directory. The processes should expect to be run in the `run/` directory. This can be very important for linking dependencies.

The reasoning for this is as follows: we want to compile all of the modules the start, since this may take time. If, however, we want to change our experiment on the fly, we simply call `load newSession`, which will change the symbolic links and allow us to start a new session immediately. 

The `foo.yaml` file contains configuration information for the process. DO NOT CONFIGURE YOUR EXPERIMENT BASED ON THE YAML FILE IN THE PROC SUBDIRECTORY. Instead, create a `foo.yaml` file in the relevant `session/` subfolder. 

### session/

A folder within session should contain all of the relevant information for running a session. For example:

```
session/cerebusTest/load.sh
session/cerebusTest/run.sh
session/cerebusTest/cerebusAdapter.yaml
session/cerebusTest/monitor.yaml
session/cerebusTest/README.md
```

At a minimum, `load.sh` would then link all of the contents of `session/cerebusTest` as well as `bin/cerebusTest` and `bin/monitor` to the `run/` folder. 

### run/

This folder should contain all of the information needed to run the session. It will also likely contain the `dump.rdb` file created by redis, and any analysis output pertaining to the run.

## yaml files

YAML files used for configuring processes can contain whatever sub-headings are needed, but at minimum should contain a key called `parameters` with the following structure:

```
parameters:
- name: bar
  value: 12345
  description: This text describes how important bar is
  static: true
```

The name of the parameter is called `bar`, and it has value `12345` (N.B. This can be a string or a number). The description is a text-field that describes how the variable is used (and potentially common values). 

Parameters can be "static" or "non-static." A static variable is one that is set during initialization and is not changed thereafter. A non-static is one that can be changed while the module is running. For instance, the host address of the Redis instance will likely be a static, whereas a boolean flag indicating whether a matrix multiplication does or doesn't occur during a module's run-cycle can be static: false. 


## Redis as a mechanism for IPC

The primary mode of inter-process communication with RANDS is using Redis, focusing on [Redis streams](https://redis.io/topics/streams-intro). Briefly, Redis is an in-memory cache key-based database entry. It solves the problem of having to rapidly create, manipulate, and distribute data in memory very quickly and efficiently. 

A stream within redis has the following organization:

```
stream_key ID key value key value ...
```


The `ID` defaults to the millisecond timestamp of when the piece of information was collected. It has the form `MMMMMMMMM-N`, where N is a number >= 0. The idea is that if there are two entries at the same millisecond timestep, they can be uniquely identified with the N value. N begins at N and increments for every simultaneously created entry within the same millisecond.

When a module wants to share data with others, it does so using a stream. There are several advantages to using a stream: 

1. Data is automatically timestamped
2. Adding new data to the stream is cheap, since it's stored internally as a linked-list. 
3. It makes it easy to have a pub/sub approach to IPC, since modules can simply call the `xread` command 
4. It makes it easy to query previously collected data using the `xrange` or `xrevrange` command. Reading new data from either the head or the tail of the stream is computationally cheap.

# Creating a new module

Modules can be written in any language. Modules are launched, and stopped, in the `run.sh` script. Conceptually, a module should [do one thing and do it well](https://en.wikipedia.org/wiki/Unix_philosophy). Modules are designed to be chained together in sequence. It should not be surprising if an experimental session applying real-time decoding to neural data would have on the order of 6-12 modules running.

At a minimum, a module should have the following characteristics:

1. Catch SIGINT to close gracefully
2. Have a `.yaml` configuration file

Since it's inpredictable how modules will be stopped during a session, it's important to have graceful process termination in the event of a SIGINT being sent to the process. This is especially important because if processes are initiated using `run.sh`, the SIGINT sent to the bash script will be propagated to the module.

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

First, *do not write a module that both sets a `SCHED_FIFO` prioritization and interacts with Redis*. The way around this is to have a process do one or the other. If a process needs to run a timer, then have the process `pause()` until if gets a signal from a different module (scheduled with SCHED_FIFO) indicating that it's time to run.

Second, *do not write a module that sets `SCHED_FIFO` that is launched from python*. The way to do this is to lanch the processes using the `run.sh` script. 

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
