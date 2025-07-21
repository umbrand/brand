#!/bin/bash

################################################
# variables graphs and sites
################################################

BRAND_BASE_DIR=$(pwd)
BRAND_MOD_DIR=$BRAND_BASE_DIR/../brand-modules/
# Check if server path exists, if not mount the disk
export SERVER_PATH=/mnt/z/Data
if [ ! -d "$SERVER_PATH" ]; then
    # Check if we're in WSL or native Linux
    if grep -qi microsoft /proc/version 2>/dev/null; then
        # WSL environment - use drvfs to mount Windows drive
        sudo mkdir -p /mnt/z && sudo mount -t drvfs Z: /mnt/z
    else
        # Native Linux environment - use different mount command or approach
        read -p "Enter username for CNPL server: " username
        sudo mkdir -p /mnt/z && sudo mount -t cifs //cnpl-drmanhattan.engin.umich.edu/share /mnt/z -o user=$username,domain=UMROOT,vers=3.0,dir_mode=0777,file_mode=0666
    fi
fi
export BRAND_BASE_DIR # save brand base dir to the environment

# Activate the rt environment to get to work
conda activate rt

# Make aliases for booter and supervisor
alias booter='sudo -E env "PATH=$PATH" python supervisor/booter.py'
alias supervisor='sudo -E env "PATH=$PATH" python supervisor/supervisor.py'

# useful alias for WSL to mount server
alias mount_server='sudo mkdir /mnt/z && sudo mount -t drvfs Z: /mnt/z'

export PATH=$(pwd)/bin:$PATH
