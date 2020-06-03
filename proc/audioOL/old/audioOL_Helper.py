# Presents OL recordings to the participant
# Here's how this is organized:
# 1) Use YAML to load an audio file into memory
# 2) Call a ffmpeg to then play the recording and then send the info to:
#     i) Audio output through ffplay
#     ii) Loop back to a pipe. To do this I need to run a C file which will sit and block on the pipe
# 3) The looped back pipe allows me to timestamp when audio recordings are happening. They are pushed to Redis

# So here's the new approach:
# 1) This python script becomes a set of tools that can be used by the bash file
# 2) The bash file launches the C file that streams it into Redis
# 3) The bash file launches the complicated ffmpeg command
# 4) The Rest Server can set a flag in Redis. The bash script sits and listens to when a change happens with the redis-cli get enable, and then toggles the stop. 
# 5) Note that communication from REST still happens through connected Redis instance. 



import subprocess
import redis
import ffmpeg
import time
import sys

sys.path.insert(1, '../../../lib/')
from redisTools import *


###########################################
## The main event
###########################################

if __name__ == '__main__':

    r = initializeRedisFromYAML('audioOL')


    # in_file = '/home/david/code/github/LPCNet/wav/Emma.pcm'

    # ffmpegCommands = ['ffmpeg' \
    #         , '-re -fflags nobuffer+flush_packets' \
    #         , '-f s16le -ac 1 -ar 16k' \
    #         , ('-i ' + in_file ) \
    #         , '-f s16le -ac 1 -ar 16k' \
    #         , '-hide_banner -nostats -loglevel panic' \
    #         , 'pipe:1' 
    #         # , '| tee /tmp/pipe'
    #         ]
    # ffplayCommands = [ 'ffplay ' \
    #         , '-hide_banner -nostats -loglevel panic' \
    #         , '-f s16le -ac 1 -ar 16k -nodisp -fflags nobuffer -probesize 32 -sync ext -']

    # ffmpegString = " ".join(ffmpegCommands)
    # ffplayString = " ".join(ffplayCommands)
    # h_ffmpeg = subprocess.Popen(ffmpegString, shell=True, stdout=subprocess.PIPE)
    # h_ffplay = subprocess.Popen(ffplayString, shell=True, stdin=h_ffmpeg.stdout)

    

    # time.sleep(5)
    # hAudio.terminate()


