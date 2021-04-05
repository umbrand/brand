#!/bin/bash
masterList=(

    # MODULES
    bin/nidaq_acquisition
    session/nidaqTesting/nidaq_acquisition.yaml

    bin/monitor
    session/nidaqTesting/monitor.yaml

    bin/timer
    session/nidaqTesting/timer.yaml

    # CONFIGURATION
    session/nidaqTesting/README.md
    session/nidaqTesting/run.sh
    session/nidaqTesting/load.sh

    # REDIS
    session/nidaqTesting/redis.realtime.conf
    session/nidaqTesting/redis.rest.conf
    lib/redis/src/redis-server
    lib/redis/src/redis-cli

    session/nidaqTesting/analyze.sh
    analysis/monitor_analysis.py
)

####################################
# Check to see if the run folder exists
####################################

if [ ! -d "run/" ]; then
    mkdir run
    echo "Creating run/ folder"
fi

####################################
# Moves the files and folders to load
####################################

pushd run

for toLink in ${masterList[*]}
do 
    if [ -L `basename $toLink` ]; then
        echo "Link $toLink exists"
    else 
        ln -s ../$toLink 
        echo "Linking $toLink"
    fi
done

popd
