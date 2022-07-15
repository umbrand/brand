#!/bin/bash

################################################
# variables graphs and sites
################################################
<<<<<<< HEAD
# list of graph names and site names
site_list=($(ls -d graphs/* | cut -d '/' -f2))
export SITE="" # current site, is empty

# tab complete for load and setSite commands
complete -W "`echo ${site_list[@]}`" setSite
=======
>>>>>>> dev

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



# Activate the rt environment to get to work
conda activate rt
