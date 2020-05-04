#!/bin/bash

# This is the script that runs the OL audio production


#######################################################
# Start by initializing Redis
#######################################################

echo "[audioOL] Starting audioOL_Helper to setup Redis variables..."
pythonOutput=`python audioOL_Helper.py`
echo -e "$pythonOutput"

# Now we grab the IP and the port information 
redisIP=`echo -e "$pythonOutput" | grep redisIP | cut -f3 -d ":" | tr -d [:space:]`
redisPort=`echo -e "$pythonOutput" | grep redisPort | cut -f3 -d ":" | tr -d [:space:]`

echo "[audioOL] Redis initialized with IP = $redisIP, Port = $redisPort"

# Now we grab the filename from Redis that we want to play
soundFileName=`redis-cli -h $redisIP -p $redisPort get fileName`
echo "[audioOL] Redis says we are going to load: $soundFileName"


#######################################################
# Now we launch Tmux and then send ffplay over and then attach it
#######################################################

echo "[audioOL] Launching tmux..."

ffplayString="ffplay -autoexit -nodisp -hide_banner $soundFileName; redis-cli -h $redisIP -p $redisPort publish soundStop \`date +'%T.%4N'\`"
# ffplayString+="kill -s INT \`pgrep audioOL.sh\`"


echo $ffplayString
tmux send-keys -t $SESSION:$WINDOW.1 "$ffplayString"
tmux send-keys -t $SESSION:$WINDOW.1 Enter
redis-cli -h $redisIP -p $redisPort publish soundStart `date +"%T.%4N"`,START

# Now inform Redis that we have started the ffmpeg


sleep 1
PID_ffplay=`pgrep ffplay`
ffplayOn=1
echo "[audioOL] ffmpeg has PID: $PID_ffplay"




#######################################################
# Helpers
#######################################################

displayMenu() {
    echo "p) Pause ffplay"
    echo "q) Quit program"
    echo ""
}

selectionPause() {

    if [ "$ffplayOn" -eq 1 ]; then
        ffplayOn=0
        # kill -s STOP $PID_ffmpeg
        kill -s STOP $PID_ffplay
        redis-cli -h $redisIP -p $redisPort lpush soundStop `date +"%T.%4N"`
    else
        ffplayOn=1
        # kill -s CONT $PID_ffmpeg
        kill -s CONT $PID_ffplay
        redis-cli -h $redisIP -p $redisPort lpush soundStart `date +"%T.%4N"`
    fi

}

handleSIGINT()  {
    # kill -s INT $PID_ffmpeg
    kill -s INT $PID_ffplay
    # kill -s INT $PID_soundPipe
    tmux kill-session
    exit 1

}

trap handleSIGINT SIGINT


#######################################################
# Main menu
#######################################################

while :
do
    displayMenu
    read -p "[audioOL] Enter any char: " -n1 char

    case $char in
    p) selectionPause ;;
    q) handleSIGINT ;;
    esac
    echo ""

done



# (ffmpeg -re -fflags nobuffer -f s16le -ac 1 -ar 16k -fflags flush_packets -i $soundFileName -f s16le -ac 1 -ar 16k pipe:1 -hide_banner -loglevel panic | tee /tmp/ffplayFIFO > /tmp/soundPipeFIFO ) &
# (ffmpeg -re -hide_banner -loglevel panic -fflags nobuffer+flush_packets -i $soundFileName -f s16le -ac 1 -ar 16k pipe:1 > /tmp/ffplayFIFO ) &
#######################################################
# Now we are going to start ffmpeg to stream the file
#######################################################

# echo "[audioOL] Launching ffmpeg as a background process"

# # (ffmpeg -re -hide_banner -loglevel panic -fflags nobuffer+flush_packets -i $soundFileName -f s16le -ac 1 -ar 16k pipe:3 -f s16le -ac 1 -ar 16k -probesize 32 pipe:4) &
# (ffmpeg -re -hide_banner -loglevel panic -fflags nobuffer+flush_packets -i $soundFileName -f s16le -ac 1 -ar 16k -probesize 32 -blocksize 2048 pipe:3 -f s16le -ac 1 -ar 16k -probesize 32 pipe:4) &

# sleep 0.5
# PID_ffmpeg=`pgrep ffmpeg`
# echo "[audioOL] ffmpeg has PID: $PID_ffmpeg"
 
# | tee /tmp/pipe | ffplay -f s16le -ac 1 -ar 16k -nodisp -fflags nobuffer -probesize 32 -sync ext - &

########################################################
## Launching the ffplay
########################################################
#echo "[audioOL] Launching ffplay as a background process"

#(ffplay -f s16le -ac 1 -ar 16k -nodisp -hide_banner -loglevel panic -fflags nobuffer+flush_packets -probesize 32 -sync ext /tmp/ffplayFIFO ) &

#PID_ffplay=`pgrep ffplay`
#ffplayOn=1
#echo "[audioOL] ffmpeg has PID: $PID_ffplay"
## Now we make the fifos and attach them to new file descriptors
#echo "[audioOL] Creating soundPipeFIFO"
#mkfifo /tmp/soundPipeFIFO 2>/dev/null
#if [ "$?" -eq 1 ]; then
#    echo "[audioOL] /tmp/soundPipeFIFO already exists."
#fi

#echo "[audioOL] Creating ffplayFIFO"
#mkfifo /tmp/ffplayFIFO 2>/dev/null
#if [ "$?" -eq 1 ]; then
#    echo "[audioOL] /tmp/ffplayFIFO already exists."
#fi
    
#exec 3<> /tmp/soundPipeFIFO
#exec 4<> /tmp/ffplayFIFO


########################################################
## Now Start the background C program that will listen to the packets created with ffmpeg
########################################################
#echo "[audioOL] Starting soundPipe to pipe data from ffmpeg to Redis..."
#./soundPipe &
#PID_soundPipe=$!
#echo "[audioOL] soundPipe has PID: $!"
