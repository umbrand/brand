#!/bin/bash

################################################
# variables graphs and sites
################################################
# list of graph names and site names
site_list=($(ls -d graphs/* | cut -d '/' -f2))
export SITE="" # current site, is empty

# tab complete for load and setSite commands
complete -W "`echo ${site_list[@]}`" setSite

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
# setting the site location
setSite() {
    # check if the specified site is valid
    if (($# < 1)); then
        >&2 echo "Please specify current location"
        return
    fi
    if [ ! $( echo ${site_list[@]} | grep -w ${1} | wc -l ) ]; then
        >&2 echo "$1 is not a valid location"
        >&2 echo "Valid locations are: " ${site_list[@]}
        return
    fi
    export SITE=$1
    graph_list=$""
    if [ $(ls graphs/$SITE/ | wc -l) -gt 0 ]; then
        graph_list=$(ls -d graphs/$SITE/* | cut -d '/' -f3)
    fi
    complete -W "`echo ${graph_list[@]}`" run

}

# hard code Emory module directory for now
setSiteEmory() {
    export SITE="../brand-modules/brand-emory"
    graph_list=$""
    if [ $(ls $SITE/graphs/ | wc -l) -gt 0 ]; then
        graph_list=$(ls -d $SITE/graphs/* | cut -d '/' -f5)
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

# Make aliases for booter and supervisor
alias booter='sudo -E env "PATH=$PATH" python -m brand.booter'
alias supervisor='sudo -E env "PATH=$PATH" python supervisor/supervisor.py'
