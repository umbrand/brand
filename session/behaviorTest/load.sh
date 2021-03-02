#!/bin/bash
masterList=(

    # REST
    #proc/rest/rest.pyx
    #proc/rest/static
    #proc/rest/templates
    #session/behaviorTest/rest.yaml 

    # MODULES
    bin/cerebusAdapter
    session/behaviorTest/cerebusAdapter.yaml

    bin/monitor 
    session/behaviorTest/monitor.yaml

    bin/timer 
    session/behaviorTest/timer.yaml

    proc/finalizeRDB/finalizeRDB.py
    session/behaviorTest/finalizeRDB.yaml

    proc/behaviorFSM/behaviorFSM.py
    session/behaviorTest/behaviorFSM.yaml

    bin/cursor_control
    session/behaviorTest/cursor_control.yaml

    # CONFIGURATION
    session/behaviorTest/README.md
    session/behaviorTest/run.sh
    session/behaviorTest/load.sh

    # REDIS
    session/behaviorTest/redis.realtime.conf
    #session/behaviorTest/redis.rest.conf
    bin/redis-server
    bin/redis-cli

    session/behaviorTest/analyze.sh
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
