#!/bin/bash
if [ -z $DISPLAY] # if there's no display
    then # then run xinit
        xinit ../../bin/cursorTargetDisplay $* -- vt$XDG_VTNR
    else # else skip it
        ../../bin/cursorTargetDisplay
fi

# code to get xinit running with our current virtual terminal number
#xinit ./cursorTargetDisplay $* -- vt$XDG_VTHR
