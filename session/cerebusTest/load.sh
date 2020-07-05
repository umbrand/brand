#!/bin/bash
masterList=(

    # REST
    proc/rest/rest.pyx
    proc/rest/static
    proc/rest/templates
    session/cerebusTest/rest.yaml 

    # MODULES
    bin/generator
    session/cerebusTest/generator.yaml

    bin/replay
    session/cerebusTest/replay.yaml

    bin/cerebusAdapter
    session/cerebusTest/cerebusAdapter.yaml

    bin/monitor 
    session/cerebusTest/monitor.yaml

    bin/timer 
    session/cerebusTest/timer.yaml

    proc/finalizeRDB/finalizeRDB.py
    session/cerebusTest/finalizeRDB.yaml

    # CONFIGURATION
    session/cerebusTest/README.md
    session/cerebusTest/run.sh
    session/cerebusTest/load.sh

    # REDIS
    session/cerebusTest/redis.realtime.conf
    session/cerebusTest/redis.rest.conf
    bin/redis-server
    bin/redis-cli

    session/cerebusTest/analyze.sh
    analysis/monitor_analysis.py
    analysis/cerebusAdapter_analysis.py
    analysis/cerebusAdapter_plot.py
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
