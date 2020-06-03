#!/bin/bash
SESSION='game'
WINDOW='audioOL'

tmux new-session -d -s $SESSION -n $WINDOW
tmux split-window -h -t $SESSION:$WINDOW
tmux send-keys -t $SESSION:$WINDOW.0 "./audioOL.sh" Enter
tmux attach -t $SESSION
tmux select-window -t $SESSION:$WINDOW

# tmux send-keys -t audioOL.1 "echo HELLO" Enter
