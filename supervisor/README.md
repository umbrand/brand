# Supervisor
> Supervisor is a core process in BRAND serving the following functions - 
1. Boots nodes
    - Boots up a single graph with all the nodes and supervisor maintains PIDs of each independently running nodes.
2. Kills nodes
    - Receives command to stop all nodes.
3. Maintain internal model of the state of the graph
    - List of nodes running and their PIDs.
    - Most recent published status of each node.

## Execution
```
$ python supervisor/supervisor.py -g <name_of_the_graph_yaml_file>
```
Can also be run without defining a graph file on start:
```
$ python supervisor/supervisor.py
```
## BRAND convention for graph yaml files
- `graph.yaml`: The graph yaml file should specify the following parameters and it's mandatory otherwise the program will not run:
    - `module`: This refers to the site module that the graph is to be run in.
    - `node name`: This refers node name within the module.
    - `version_name`: This refers to the version of the node.

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
                |---<module-name>_nodename.out
                |---Makefile   
        |
        |---<graphs>
            |
            |---<graphname.yaml>
            |---<graphname.pptx>
```

## Utilities structure
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



## Graph 


## Working logic of the supervisor
```
1. Parses the command line arguments for a valid graph yaml file.
2. Reads the graph yaml file and creates a graph dictionary.
3. A redis instance is created based on the host and port specified in the graph yaml file and the redis instance is connected to the redis server. 
4. The model is published on a redis stream.
5. A redis listener is created to listen to the stream and when a message is received either for startGraph or stopGraph, the message is parsed and the corresponding command is executed.
6. If the command is startGraph, the node is Steps 1-5 are repeated for each node in the graph and each node runs as independent child processes.
7. If the command is stopGraph, all the child processes are killed and the graph is stopped.
```
## Redis Streams
- `graph_status`: This stream is used to publish the status of the graph (XADD).
- `supergraph_stream`: This stream is used to publish the model (XADD).
- `<node_nickname>_data`: This stream is used to reading the data of the node being run (XREAD).
- `<node_nickname>_output`: This stream is used to process the data or convert the raw data to be run on output stream (XADD).
- `supervisor_ipstream`: This stream is used to listen to commands startGraph and stopGraph for the supervisor (XREAD).

## Redis Commands
Commands can be sent to the supervisor through Redis using the following syntax: ```xadd supervisor_ipstream * commands <command_name> [<arg_key> <arg_value>]```. The following commands are currently implemented:
1. ```startGraph [file <path_to_file>]```: Start graph from file defined on start up. If graph file wasn't supplied on start up, must be defined here.
2. ```stopGraph```: Stop graph, by stopping the processes for each running node.


## Typical usage
Run this before graph: ```$python3 -m pip install -r supervisor/requirements.txt``` to install required packages.
1. ```$python3 supervisor/supervisor.py -g graph.yaml```
2. Redis server is started.
3. Start the graph using command ```$xadd supervisor_ipstream * commands startGraph```
4. Check the model published on the model stream using command ```$xrevrange supergraph_stream + - count 1```
5. Check the status of the graph anytime using command ```$xrevrange graph_status + - count 1```
6. Update of parameters on the go can be done by using command ```xadd supervisor_ipstream * commands startGraph file <path_to_file>```
7. Stop the graph using command ```$xadd supervisor_ipstream * commands stopGraph```. 

## Supervisor glossary
`parse_vargs`:
Parses the command line arguments using `argparse` module and checks if the graph yaml file has been loaded and if it's valid.he graph yaml file and returns a graph dictionary.

`search_node_yaml_file`: returns a yaml file based on module, name and version of the node.

`search_node_bin_file`: returns a binary file based on module, name and version of the node (currently has been disabled since there wasn't an executable file for the node).

`load_graph`:  comprises of the working logic behind the supervisor. Creates the model of the graph and starts the nodes after rule checking and validation.

`start_graph`: starts the graph by calling the `load_graph` function after validation of rules and types/names/value in the node parameters.
Publishes a model of the graph on the redis stream using XADD and forks parent process to create more child processes for the nodes. 

`stop_graph`: stops the graph by killing all the child processes.

`parseCommand` : parses the redis-cli commands for starting and stopping the graph.

`read_commands_from_redis`: reads the redis-cli commands from the redis stream.

## Known issues
None as of now.
