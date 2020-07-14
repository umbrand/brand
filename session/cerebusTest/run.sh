#!/bin/bash

start_modules=(cerebusAdapter)
main_modules=(monitor)
end_modules=(finalizeRDB.py)

##############################################
# Check to see if there is already an .rdb file
##############################################

if [ -f "dump.rdb" ]; then
    echo ""
    echo "---------------------------------------------"
    echo "---------------------------------------------"
    echo "Warning. There is already a dumb.rb file."
    echo "This suggests that redis has recently been run"
    echo "There may be existing data from a previously recorded session"
    echo ""
    echo "Are you sure you want to continue? (yes/no)"

    read should_continue

    if [[ $should_continue != "yes" ]]; then
        echo "Exiting."
        return
    fi
fi


##############################################
# Load the modules
##############################################

./redis-server redis.realtime.conf &
sleep 2s

echo "--------------------------------"
echo "Loading start modules"
echo "--------------------------------"

for proc in ${start_modules[*]}
do
    ./$proc &
    sleep 1s
done

echo "--------------------------------"
echo "Loading main modules"
echo "--------------------------------"

for proc in ${main_modules[*]}
do
    ./$proc &
    sleep 1s
done

echo "--------------------------------"
echo "Starting timer"
echo "--------------------------------"

./timer &
sleep 1s

echo "--------------------------------"
echo "Waiting"
echo "--------------------------------"

userInput=""
while [[ "$userInput" != "q" ]]
do
    echo "Type q to quit"
    read userInput
done


echo "--------------------------------"
echo "Shutting down timer"
echo "--------------------------------"

pkill -SIGINT timer
sleep 1s


echo "--------------------------------"
echo "Shutting down modules"
echo "--------------------------------"

for proc in ${main_modules[*]}
do
    pkill -SIGINT $proc
    sleep 1s
done

for proc in ${start_modules[*]}
do
    pkill -SIGINT $proc
    sleep 1s
done

echo "--------------------------------"
echo "Loading finalize modules"
echo "--------------------------------"

for proc in ${end_modules[*]}
do
    ./$proc &
    sleep 1s
done

echo "--------------------------------"
echo "Shutting down redis"
echo "--------------------------------"

./redis-cli save

pkill -SIGINT redis-server


