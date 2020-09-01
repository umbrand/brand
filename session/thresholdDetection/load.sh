#!/bin/bash
masterList=(

    # REST
    proc/rest/rest.pyx
    proc/rest/static
    proc/rest/templates
    session/thresholdDetection/rest.yaml 

    # MODULES
    bin/cerebusAdapter
    session/thresholdDetection/cerebusAdapter.yaml

    bin/monitor
    session/thresholdDetection/monitor.yaml

    bin/timer 
    session/thresholdDetection/timer.yaml

    proc/thresholdExtraction/thresholdExtraction.py
    session/thresholdDetection/thresholdExtraction.yaml

    proc/finalizeRDB/finalizeRDB.py
    session/thresholdDetection/finalizeRDB.yaml

    # CONFIGURATION
    session/thresholdDetection/README.md
    session/thresholdDetection/run.sh
    session/thresholdDetection/load.sh

    # REDIS
    session/thresholdDetection/redis.realtime.conf
    session/thresholdDetection/redis.rest.conf
    lib/redis/src/redis-server
    lib/redis/src/redis-cli

    session/thresholdDetection/analyze.sh
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
