# Emory real-time rig
## Building
### Requirements
* Host Machine Running Ubuntu 18.04
* Nvidia GPU with Compute Capabilities > ?
* CUDA 10.0
* [Anaconda3](https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html) for Linux

### Environment Setup and Make
`bootstrap.sh` is provided to automate the environment setup. It installs debian pkg dependencies using `apt-get` and creates the real-time conda environment (rt), which is defined by `environment.yaml`. [LPCNet](https://github.com/mozilla/LPCNet/) and [hiredis](https://github.com/redis/hiredis) have been included as submodules, which also get initialized by `bootstrap.sh`. After running bootstrap you simply need to run `make` at the project root. This will build all the project binaries, including submodule dependencies, and output them to `bin/`. Be sure to activate the conda env before running make as Makefiles dependent on cython require it.
```
./boostrap.sh
conda activate rt
make
```

# Folder organization

The primary organization of the rig is:

```
lib/
proc/
session/
run/
```


## lib/

lib/ contains a series of libraries or helper functions needed to make the system work. For instance, here's an example of two folders:

```
lib/hiredis
lib/utilityFunctions
```

hiredis is a submodule that links to a different git respository. utilityFunctions is an in-house folder.

## proc/

A module is designed to solve a specific task. The `proc/` folder contains the modules used for the rig. Suppose we call our module `foo`. Then, the contents of the foo module should have, at minimum, the following:

```
proc/foo/foo
proc/foo/foo.yaml
proc/foo/README.md
```

`proc/foo/foo` is an executable that runs the module; the `foo.yaml` contains configuration information for the process, and the README.md contains information (describing the purpose of the module, what it produces and what it consumes, how data can be interpreted, etc.)

The rig assumes that `foo` will be executable as `./foo`. However, it's language agonistic, so if you want to write a process in C, python, bash, etc., it doesn't matter, as long as it can be executed with a ./foo command (if you're not compiling your code, just make sure to add the appropriate shebang).

The root-level YAML structure can contain whatever sub-headings are needed, but at minimum should contain an entry called parameters with the following structure:

```
parameters:
- name: bar
  value: 12345
  description: This text describes how important bar is
  static: true
```

The name of the parameter is called bar, and it has value 12345 (N.B. This can be a string or a number). The description is a text-field that describes how the variable is used (and potentially common values). 

Parameters can be "static" or "non-static." A static variable is one that is set during initialization and is not changed thereafter. A non-static is one that can be changed while the module is running. For instance, the host address of the Redis instance will likely be a static, whereas a boolean flag indicating whether a matrix multiplication does or doesn't occur during a module's run-cycle can be static: false. 

## IPC

The primary mode of inter-process communication through the rig is through Redis, focusing on Redis streams. If you're not familiar with Redis or Redis streams, check out this link for information. Briefly, Redis is an in-memory cache key-based database entry. It solves the problem of having to rapidly create, manipulate, and distribute data in memory very quickly and efficiently. 

A stream within redis has the following organization:

```
stream_key ID key value key value ...
```


The `ID` defaults to the millisecond timestamp of when the piece of information was collected. It has the form `MMMMMMMMM-N`, where N is a number >= 0. The idea is that if there are two entries at the same millisecond timestep, they can be uniquely idenfied with the N value. 

When a module wants to share data with others, it does so using a stream. There are several advantages to using a stream: 

1. Data is automatically timestamped
2. Adding new data to the strema is cheap, since it's stored internally as a linked-list
3. It makes it easy to have a pub/sub approach to IPC, since modules can simply call the `xread` command 
4. It makes it easy to query previously collected data using the xrange/xrevrange command





## session/

The rig has the concept of a "session", which is short for experimental session or just experiment. That is, it contains all of the conceptual information to run a specific kind of experiment.

Suppose we call our session "tracking." Then, the first folder will have the name `session/tracking.0`

Where 0 refers to the version of the experiment. For the purposes of session development, a new version of a session should be created whenever any of the folder contents have been altered after having been run in the wild. For instance, if JS ran a "tracking" experiment on day 1, and then had to revise some parameters or even create a new module for day 2 (but the goals of the experiments haven't changed) then that would call for the creation of a new folder: JS.tracking.1. 

Continuing on with this example, the folder will have the following contents:

```
session/tracking.0/session.yaml
session/tracking.0/logger.yaml
session/tracking.0/streamUDP.yaml
```

Immediately, you can see that there are custom configuration files for the logger and streamUDP modules, hinting that both will be used as part of the session. The session.yaml file keeps a list of the modules to be used for the session.



Logging data
==============

Modules that stream data create new information and it is automatically timestamped. When the experiment is done (or even when it is happening, if you want?) the logger begins by going through a list of streams and turning the data into a SQL table. 


