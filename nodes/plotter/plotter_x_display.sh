#!/bin/bash

if [ -z $DISPLAY ] # if there's no display
    then # then run xinit
        echo "trying to connect with X"
        xinit python3 "./oscil.py" $* -- vt$XDG_VTNR
    else # else skip it
        python3 ./plotter.py $*
fi


