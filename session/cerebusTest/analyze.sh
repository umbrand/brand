#!/bin/bash

modules=(cerebusAdapter_analysis.py  monitor_analysis.py)

./redis-server redis.realtime.conf &

for module in ${modules[*]}
do
    python $module
done

pkill redis-server
