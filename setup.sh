#!/bin/bash

################################################
# variables graphs and sites
################################################
# list of graph names and site names
site_list=($(ls -d graphs/* | cut -d '/' -f2))
export SITE="" # current site, is empty

# tab complete for load and setSite commands
complete -W "`echo ${site_list[@]}`" setSite

# list of module names
module_list=($(ls -d ../brand-modules/* | cut -d '/' -f3))

# tab complete for setModule command
complete -W "`echo ${module_list[@]}`" setModule

# rdb save location -- saving to an environment variable to be useful 
# for different shells run at the same time
if [ -z ${RDB_SAVE_DIR} ]; then # if it doesn't exist, set to a default
RDB_SAVE_DIR="../BRANDS_rdb"
fi
if [ ! -d ${RDB_SAVE_DIR} ]; then # if the directory doesn't exist, create it
    mkdir ${RDB_SAVE_DIR}
fi
export RDB_SAVE_DIR # push up to the environment

BRAND_BASE_DIR=$(pwd)
export BRAND_BASE_DIR # save brand base dir to the environment

# create directory for redis socket
if [ ! -d "/var/run/redis" ]; then # if the directory doesn't exist, create it
    sudo mkdir "/var/run/redis"
fi
sudo chmod -R 777 "/var/run/redis"

################################################
# defining functions
################################################


# Define external module (site) for Makefile
setModule() {
    # error if no module argument is specififed
    if (($# < 1)); then
        >&2 echo "Please specify a module"
        return
    fi
    if [ ! $( echo ${module_list[@]} | grep -w ${1} | wc -l ) ]; then
        >&2 echo "$1 is not a valid module"
        >&2 echo "Valid modules are: " ${module_list[@]}
        return
    fi    
    export SITE="$1"
    graph_list=$""
    if [ $(ls ../brand-modules/$SITE/graphs/ | wc -l) -gt 0 ]; then
        graph_list=$(ls -d ../brand-modules/$SITE/graphs/* | cut -d '/' -f5)
    fi
    complete -W "`echo ${graph_list[@]}`" run

}


# hard code Emory module directory for now
setSiteEmory() {
    export SITE="brand-emory"
    graph_list=$""
    if [ $(ls ../brand-modules/$SITE/graphs/ | wc -l) -gt 0 ]; then
        graph_list=$(ls -d ../brand-modules/$SITE/graphs/* | cut -d '/' -f5)
    fi
    complete -W "`echo ${graph_list[@]}`" run

}



# creating a new graph
createGraph () {
    # check if a site name has been declared
    if [[ "$SITE" == "" ]]; then
        >&2 echo "Please designate your current site using the setSite function"
        return
    fi
    if (( $# < 1)); then
        >&2 echo "No graph name specified."
        return
    fi
    mkdir ./graphs/$SITE/$1
    cp ./graphs/templateLocation/templateGraph/templateGraph.yaml ./graphs/$SITE/$1/$1.yaml
    cp ./graphs/templateLocation/templateGraph/redis.templateGraph.conf ./graphs/$SITE/$1/redis.$1.conf

    graph_list=$(ls -d graphs/$SITE/* | cut -d '/' -f3)
    complete -W "`echo ${graph_list[@]}`" run
}


# Activate the rt environment to get to work
conda activate rt
load () {
   ./graphs/sharedDevelopment/$1/load.sh
}

run () {
    pushd run
    sudo -E env "PATH=$PATH" ./run.sh $1
    popd
}

#analyze () {
#    pushd run
#    ./analyze.sh
#    popd
#}
