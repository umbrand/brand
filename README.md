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

# Sessions

The real-time rig has the concept of a "session", which is short for experimental session. A session folder contains all of the information needed to run an experiment. Suppose we call our session "tracking." Then, the first folder will have the name `session/tracking.0`. The `0` refers to the version of the experiment. For the purposes of session development, a new version of a session should be created whenever any of the folder contents have been altered after having been run in the wild. 

The information about running a session is defined in the `session.yaml` file. Here's an example of a configuration for the `tracking.0` session: 

```
modules:
  start:
   - name: rest.pyx
     links: 
      - proc/rest/rest.pyx
      - proc/rest/static
      - session/tracking.0/rest.yaml 
  main:
   - name: timer
     links: 
      - bin/timer 
      - session/tracking.0/timer.yaml
      - bin/generator
      - session/tracking.0/generator.yaml
      - bin/streamUDP
      - session/tracking.0/streamUDP.yaml
  end:
   - name: logger.py
     links: 
      - proc/logger/logger.py
      - session/tracking.0/logger.yaml

files:
 - session/debug/README.md
 - session/debug/session.yaml
```

A session has three stages: `start`, `main`, and `end`. Modules run in the `start` stage should be supportive. For example, these modules may handle incoming UDP information, recreate previously collected data, manage a rest server, etc. The modules in the `main` stage do the bulk of the work. Finally, when the program exits, it first shuts down `main` and `start` modules, and then runs the `end` modules.

The modules have a name and then series of links. The links refer to the source files needed to run the modules. For example, the `rest.pyx` module will symbolically link the following files to `run/`: `proc/rest/rest.pyx`, `proc/rest/static`,`session/tracking.0/rest.yaml`.

By looking at the list of links, one gets a sense of dependencies and where they're coming from. Good coding practice is to define all of the .yaml files needed to run modules within the session folder. 

### Running a session

After running `make`, there will be binaries located in the `bin/` folder. The next step is to initialize the files needed to run a session. Continuing with our example:

```
python rig.py initialize tracking.0
```

Will then copy the files defined in `session/tracking.0/session.yaml` to the `run/` folder. To run an experiment, type:

```
python rig.py run
```

This will look at `run/session.yaml` (which was linked to `session/tracking.0/session.yaml`) and then run the appropriate scripts to start the experiment.

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

`bin/` contains the compiled output of the various processes. To compile a process, run `make [process]` from the root directory.

### lib/

lib/ contains a series of libraries or helper functions needed to make the system work. Here's are examples of two folders:

```
lib/hiredis
lib/redisTools
```

`hiredis` is a submodule that links to a different git respository. `redisTools` is an in-house folder that has some wrapper functions for working with redis.

### proc/

A module is designed to solve a specific task. The `proc/` folder contains the modules used for the rig. Suppose we call our module `foo`. Then, the contents of the foo module should have, at minimum, the following:

```
proc/foo/foo
proc/foo/foo.yaml
proc/foo/README.md
```

`proc/foo/foo` is an executable that runs the module; the `foo.yaml` contains configuration information for the process, and the README.md contains information describing the purpose of the module, what it produces and what it consumes, how data can be interpreted, etc.

The root-level YAML structure can contain whatever sub-headings are needed, but at minimum should contain an entry called parameters with the following structure:

```
parameters:
- name: bar
  value: 12345
  description: This text describes how important bar is
  static: true
```

The name of the parameter is called `bar`, and it has value `12345` (N.B. This can be a string or a number). The description is a text-field that describes how the variable is used (and potentially common values). 

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


Logging data
==============

Modules that stream data create new information and it is automatically timestamped. When the experiment is done (or even when it is happening, if you want?) the logger begins by going through a list of streams and turning the data into a SQL table. 


