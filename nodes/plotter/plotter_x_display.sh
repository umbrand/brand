#!/bin/bash

if [ -z $DISPLAY ] # if there's no display
    then # then run xinit
        echo "trying to connect with X"
        xinit ../../bin/plotter $* -- vt$XDG_VTNR
    else # else skip it
        python3 ./plotter.py $*
fi


