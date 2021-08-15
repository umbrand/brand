#!/bin/bash
masterList=(
    # MODULES
    bin/timer
    proc/timer/timer.yaml

    bin/publisher
    session/loadTest/publisher.yaml

    bin/subscriber
    proc/subscriber/subscriber.yaml

    # CONFIGURATION
    session/loadTest/run.sh
    session/loadTest/load.sh

    # REDIS
    session/loadTest/redis.realtime.conf
    bin/redis-server
    bin/redis-cli

    # ANALYSIS
    session/loadTest/analyze_load_test.py
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
