#!/bin/bash
if [ -z $DISPLAY] # if there's no display
    then # then run xinit
        #xinit ../nodes/cursorTargetDisplay/cursorTargetDisplay.bin $* -- vt$XDG_VTNR &
        xinit ./cursorTargetDisplay.bin $* -- vt$XDG_VTNR &
    else # else skip it
        ./cursorTargetDisplay.bin
fi

# code to get xinit running with our current virtual terminal number
#xinit ./cursorTargetDisplay $* -- vt$XDG_VTHR
