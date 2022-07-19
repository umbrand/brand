#!/bin/bash

################################################
# variables graphs and sites
################################################

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

# Make aliases for booter and supervisor
alias booter='sudo -E env "PATH=$PATH" python -m brand.booter'
alias supervisor='sudo -E env "PATH=$PATH" python supervisor/supervisor.py'

export PATH=$(pwd)/bin:$PATH
