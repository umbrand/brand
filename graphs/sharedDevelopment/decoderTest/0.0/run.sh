#!/bin/bash

start_modules=()
main_modules=(decoder udp_send)
end_modules=()

##############################################
# Check to see if there is already an .rdb file
##############################################

RED="\e[31m"
YELLOW="\e[33m"
DEFAULT="\e[39m"

error () {
    echo -e "${RED}Error: ${DEFAULT}$1"
    exit 1
}

warn () {
    echo -e "${YELLOW}Warning: ${DEFAULT}$1"
}

# make sure the database save name is defined in the redis cfg file and not commented out
redis_cfg=redis.realtime.conf
rdb=`grep "dbfilename.*rdb" ${redis_cfg} | grep -v "#" | awk '{print $2}'`
[ -z "${rdb}" ] && error "No database filename given in ${redis_cfg}"
[ `echo ${rdb} | wc -l` -gt 1 ] && error "dbfilename is defined multiple times in $redis_cfg}"

if [ -f "${rdb}" ]; then
    # If the database already exists, increment the filename according to ${rdb}_x,
    # where x is the number of replacements that have been issued for ${rdb}.

    # extract x from rdb name. x=0 means we haven't done this before.
    prefix=${rdb%%.rdb} #everything before '.rdb'
    let x=`echo ${prefix} | rev | cut -d '_' -f 1 | rev`
    [ $x -gt 0 ] && prefix=`echo ${rdb} | sed 's/\(.*\)_.*/\1/'` # everything before the last '_'
    x=$(( $x + 1 )) # increment the count
    while [ -f "${prefix}_$x.rdb" ]; do
        x=$(( $x + 1 ))
    done
    new_rdb=${prefix}_$x.rdb

    msg="There is already a database saved as ${rdb}.\n"
    msg="${msg}The database from this run will be saved as ${new_rdb}."
    warn "${msg}"
    read -p "Do you want to continue? [Y/n]: " should_continue

    if [[ ${should_continue,,} != "y"* ]]; then
        echo "Exiting."
        exit
    fi
    rdb=${new_rdb}
fi


##############################################
# Load the modules
##############################################

./redis-server ${redis_cfg} --dbfilename ${rdb} &
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
echo "Running function generator"
echo "--------------------------------"

./func_generator

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

# for debugging
# echo "--------------------------------"
# echo "Waiting"
# echo "--------------------------------"

# userInput=""
# while [[ "$userInput" != "q" ]]
# do
#     echo "Type q to quit"
#     read userInput
# done

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


