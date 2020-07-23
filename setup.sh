#!/bin/bash

# Generate an array of all folders within session
session_list=($(ls -d session/* | cut -d '/' -f2))
complete -W "`echo ${session_list[@]}`" load

# Activate the rt environment to get to work
conda activate rt


load () {
    ./session/$1/load.sh
}

run () {
    pushd run
    ./run.sh
    popd
}

analyze () {
    pushd run
    ./analyze.sh
    popd
}
