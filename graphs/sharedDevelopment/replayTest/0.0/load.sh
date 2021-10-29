#!/bin/bash
masterList=(
    # MODULES
    bin/func_generator
    bin/decoder
    bin/decoder_trainer
    bin/udp_send

    nodes/decoder_trainer/model.json

    # CONFIGURATION
    graphs/sharedDevelopment/replayTest/0.0/run.sh
    graphs/sharedDevelopment/replayTest/0.0/load.sh
    graphs/sharedDevelopment/replayTest/0.0/replayTest.yaml

    # REDIS
    graphs/sharedDevelopment/replayTest/0.0/redis.realtime.conf
    bin/redis-server
    bin/redis-cli

    # ANALYSIS
    graphs/sharedDevelopment/replayTest/0.0/export.py
    graphs/sharedDevelopment/replayTest/0.0/analyze_decoder_sweep.py
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
