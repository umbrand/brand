#!/bin/bash

# Generate an array of all folders within session
graph_list=($(ls -d graphs/*/* | cut -d '/' -f3))
location_list=($(ls -d graphs/* | cut -d '/' -f2))
complete -W "`echo ${graph_list[@]}`" load
complete -W "`echo ${location_list[@]}`" createGraph

# creating a new graph
createGraph () {
    # needs an input of the location and the graph name
    if (( $# < 1)); then 
        >&2 echo "Please specify a location"
        >&2 echo "Current locations are: " $location_list
        return
    fi
    if (( $# < 2)); then
        >&2 echo "No graph name specified."
        >&2 echo "creating graph with name DEFAULT"
        $2 = "DEFAULT"
    fi
    mkdir ./graphs/$1/$2/0.0
    cp ./graphs/templateLocation/templateGraph/0.0/templateGraph.yaml ./graphs/$1/$2/0.0/$2.yaml
    
}


# Activate the rt environment to get to work
conda activate rt


load () {
    ./graphs/$1/load.sh
}

run () {
    pushd run
    sudo -E env "PATH=$PATH" ./run.sh
    popd
}

analyze () {
    pushd run
    ./analyze.sh
    popd
}
