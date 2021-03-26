#!/bin/bash
masterList=(

    # REST
    #proc/rest/rest.pyx
    #proc/rest/static
    #proc/rest/templates
    #session/mouseBehaviorTest/rest.yaml 

    # MODULES
    bin/monitor 
    session/mouseBehaviorTest/monitor.yaml

    bin/timer 
    session/mouseBehaviorTest/timer.yaml

    proc/finalizeRDB/finalizeRDB.py
    session/mouseBehaviorTest/finalizeRDB.yaml

    proc/behaviorFSM/behaviorFSM.py
    session/mouseBehaviorTest/behaviorFSM.yaml

    bin/cursorTargetDisplay
    session/mouseBehaviorTest/cursorTargetDisplay.yaml

    bin/mouse_ac
    session/mouseBehaviorTest/mouse_ac.yaml


    # CONFIGURATION
    session/mouseBehaviorTest/README.md
    session/mouseBehaviorTest/run.sh
    session/mouseBehaviorTest/load.sh

    # REDIS
    session/mouseBehaviorTest/redis.realtime.conf
    #session/mouseBehaviorTest/redis.rest.conf
    bin/redis-server
    bin/redis-cli

    session/mouseBehaviorTest/analyze.sh
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
