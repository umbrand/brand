#!/bin/bash
masterList=(
    # MODULES
    bin/timer 
    session/mouseTest/timer.yaml

    bin/redis_test
    proc/mouse_read/redis_test.yaml

    bin/mouseAdapter
    proc/mouse_read/mouseAdapter.yaml

    bin/cursor_control
    proc/cursor_control/cursor_control.yaml
    proc/cursor_control/yellow_circle.png

    # REDIS
    session/mouseTest/redis.realtime.conf
    bin/redis-server
    bin/redis-cli

    session/mouseTest/analyze.sh

    session/mouseTest/run.sh
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

