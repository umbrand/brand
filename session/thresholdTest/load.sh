#!/bin/bash
masterList=(

    # REST
    proc/rest/rest.pyx
    proc/rest/static
    proc/rest/templates
    session/thresholdTest/rest.yaml 

    # MODULES
    bin/cerebusAdapter
    session/thresholdTest/cerebusAdapter.yaml

    bin/monitor
    session/thresholdTest/monitor.yaml

    bin/timer 
    session/thresholdTest/timer.yaml

    proc/thresholdExtraction/thresholdExtraction.py
    session/thresholdTest/thresholdExtraction.yaml

    proc/finalizeRDB/finalizeRDB.py
    session/thresholdTest/finalizeRDB.yaml

    # CONFIGURATION
    session/thresholdTest/README.md
    session/thresholdTest/run.sh
    session/thresholdTest/load.sh

    # REDIS
    session/thresholdTest/redis.realtime.conf
    session/thresholdTest/redis.rest.conf
    lib/redis/src/redis-server
    lib/redis/src/redis-cli

    session/thresholdTest/analyze.sh
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
