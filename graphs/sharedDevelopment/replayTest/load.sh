#!/bin/bash
masterList=(
    # MODULES
    nodes/redis_replay/redis_replay.bin
    nodes/ffn_decoder/ffn_decoder.bin

    # CONFIGURATION
    graphs/sharedDevelopment/replayTest/run.sh
    graphs/sharedDevelopment/replayTest/load.sh
    graphs/sharedDevelopment/replayTest/replayTest.yaml
    graphs/sharedDevelopment/replayTest/stream_spec.yaml

    # REDIS
    graphs/sharedDevelopment/replayTest/redis.realtime.conf
    bin/redis-server
    bin/redis-cli

    # ANALYSIS
    graphs/sharedDevelopment/replayTest/train_ffn_decoder.py
    graphs/sharedDevelopment/replayTest/analyze_ffn_decoder.py

    # DATA
    graphs/sharedDevelopment/replayTest/20211112T1546_pop.rdb
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
