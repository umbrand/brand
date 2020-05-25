#!/bin/bash

# This script will install debian pkg dependencies and activate
# the reat-time conda environment (rt) defined by environment.yaml

# Notes
#   - this has only been tested on Ubuntu 18.04
#   - libevent-2.1-6 was already installed on my machine,
#     so assuming it comes default with Ubuntu 18.04

RED="\e[31m"
GREEN="\e[32m"
DEFAULT="\e[39m"

error () {
    echo -e "${RED}Error: ${DEFAULT}$1"
    exit 1
}

info () {
    echo -e "${GREEN}$1${DEFAULT}"
}

checkStatus () {
    [ "$1" == "0" ] || error "$2"
}

# install dependencies - so far only libsqlite3
if ! dpkg --get-selections | grep -q libsqlite3-dev; then
    info "Installing libsqlite3"
    sudo apt-get update
    sudo apt-get -y install libsqlite3-dev
    checkStatus $? "failed to install dependencies"
    info "Successfully install libsqlite3"
fi

# check conda is installed
# which conda should return a path of > 0 length if installed
[ "`which conda`" ] || error "conda is not installed. Please install it and rerun this script"

# create conda env from file - in case it has been created, just update it.
info "Updating real-time conda env"
conda env update --file environment.yaml --prune
checkStatus $? "conda update failed"
info "Your environment is ready!"
