#!/bin/bash
masterList=(
    # MODULES
    bin/timer 
    session/pygletMouse/timer.yaml

    bin/redis_test
    proc/mouse_read/redis_test.yaml

    bin/mouseAdapter
    proc/mouse_read/mouseAdapter.yaml

    bin/pyglet_display
    proc/pyglet_display/pyglet_display.yaml

    # REDIS
    session/pygletMouse/redis.realtime.conf
    bin/redis-server
    bin/redis-cli

    session/pygletMouse/analyze.sh

    session/pygletMouse/run.sh
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

