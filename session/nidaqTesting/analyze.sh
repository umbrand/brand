#!/bin/bash

modules=(monitor_analysis.py)

./redis-server redis.realtime.conf &

sleep 30


for module in ${modules[*]}
do
    python $module
done

pkill redis-server
