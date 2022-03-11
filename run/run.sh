#!/bin/bash


# check to see if we're in the right environment, and if not run setup.sh
if [ ${CONDA_DEFAULT_ENV} != "rt" ]; then
source setup.sh
fi








##############################################
# set up colors and warnings
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


##############################################
# input verification etc
##############################################
if [ "$#" -lt 1 ]; then # if no graph name given
    error "No Graph Specified"
fi

echo "${SITE}" 
if [ ! -d "../graphs/${SITE}/${1}" ]; then
    error "Invalid Graph Name"
fi


##############################################
# set up the save rdb name
##############################################
# save the file in the save directory
redis_cfg=../graphs/${SITE}/${1}/redis.${1}.conf
graphCfg=../graphs/${SITE}/${1}/${1}.yaml
partID=`grep "participant_id: " ${graphCfg} | awk '{print $2}'`
rdb="`date +"%Y%m%dT%H%M"`_${partID}.rdb"


##############################################
# get node names from the graph file
##############################################
start_nodes=`python -m brand.tools $graphCfg --stage start`
IFS=' ' read -ra start_nodes <<< "$start_nodes"
main_nodes=`python -m brand.tools $graphCfg --stage main`
IFS=' ' read -ra main_nodes <<< "$main_nodes"
end_nodes=`python -m brand.tools $graphCfg --stage end`
IFS=' ' read -ra end_nodes <<< "$end_nodes"


start_nodes_pid=()
main_nodes_pid=()

##############################################
# Load the nodes
##############################################

./redis-server ${redis_cfg} --dbfilename ${rdb} --dir ../${RDB_SAVE_DIR} &
sleep 2s

echo "--------------------------------"
echo "Loading start modules"
echo "--------------------------------"

for proc in ${start_nodes[*]}
do
    module_name=`echo $proc | cut -d '.' -f1`
    pushd ../nodes/$module_name 1>/dev/null
    ./$proc ../$graphCfg &
    ppid=`pgrep $module_name`
    start_nodes_pid+="$ppid "
    sleep 1s
    renice -20 $ppid
    popd 1>/dev/null
done

echo "--------------------------------"
echo "Loading main modules"
echo "--------------------------------"

for proc in ${main_nodes[*]}
do
    module_name=`echo $proc | cut -d '.' -f1`
    pushd ../nodes/$module_name 1>/dev/null
    ./$proc ../$graphCfg &
    main_nodes_pid+="$ppid "
    ppid=$!
    sleep 1s
    renice -20 $ppid
    popd 1>/dev/null
done

#echo "--------------------------------"
#echo "Starting timer"
#echo "--------------------------------"
#
#./timer &
##sleep 1s

echo "--------------------------------"
echo "Waiting"
echo "--------------------------------"

userInput=""
while [[ "$userInput" != "q" ]]
do
    echo "Type q to quit"
    read userInput
done


#echo "--------------------------------"
#echo "Shutting down timer"
#echo "--------------------------------"
#
#pkill -SIGINT timer
#sleep 1s
#

echo "--------------------------------"
echo "Shutting down modules"
echo "--------------------------------"


for proc_pid in ${main_nodes_pid[*]}
do
    kill -SIGINT ${proc_pid}
    sleep 1s
done

for proc_pid in ${start_nodes_pid[*]}
do
    kill -SIGINT $proc_pid
    sleep 1s
done

echo "--------------------------------"
echo "Loading finalization modules"
echo "--------------------------------"

for proc in ${end_nodes[*]}
do
    module_name=`echo $proc | cut -d '.' -f1`
    pushd ../nodes/$module_name 1>/dev/null
    ./$proc ../$graphCfg
    sleep 1s
    popd 1>/dev/null
done

echo "--------------------------------"
echo "Shutting down redis"
echo "--------------------------------"

./redis-cli save

pkill -SIGINT redis-server


