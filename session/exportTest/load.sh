#!/bin/bash
masterList=(

    # MODULES
    session/exportTest/exportNWB.py
    session/exportTest/exportNWB.yaml
    

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
