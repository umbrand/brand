# Code to play a sound recording
# The idea is that we send a stream output whenever the file starts, stops, and then ends
#
# David Brandman, May 2020

import subprocess
import redis
import ffmpeg
import time
import sys
import signal
import os
import curses

# Pathway to get redisTools.py
sys.path.insert(1, '../../lib/redisTools/')
from redisTools import get_parameter_value


# https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
# https://stackoverflow.com/questions/34497323/what-is-the-easiest-way-to-detect-key-presses-in-python-3-on-a-linux-machine

YAML_FILE = "audioOL.yaml"

def main(stdscr):
    """checking for keypress"""
    stdscr.nodelay(True)  # do not wait for input when calling getch
    return stdscr.getch()

if __name__ == "__main__":

# First, get the redis_ip and redis_port information to instantiate our instance

    redis_ip = get_parameter_value(YAML_FILE,"redis_ip")
    redis_port = get_parameter_value(YAML_FILE,"redis_port")
    print("[audioOL] Initializing Redis with IP :" , redis_ip, ", port: ", redis_port)
    r = redis.Redis(host = redis_ip, port = redis_port, db = 0)

# Next get the filename we want to load

    filename = get_parameter_value(YAML_FILE, "filename")
    print("[audioOL] Attempted to play file: ", filename)
    
# Populate the command we want to send to ffplay.
# autoexit : exit when the file has finished playing
# hide_banner : Hide the intro material 
# loglevel panic : Don't display anything unless there's an issue

    ffplayString = ["ffplay" \
            , "-autoexit -nodisp -hide_banner -loglevel panic" \
            , filename]
    ffplayString = " ".join(ffplayString)
    print("[audioOL] Executing: ", ffplayString)
    h_ffplay = subprocess.Popen(ffplayString, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)

# Prepopulate the various states we can be in

    audioOL_start = { "status" : ("start " + filename)}
    audioOL_end   = { "status" : ("end "   + filename)}
    audioOL_stop  = { "status" : ("stop "  + filename)}
    audioOL_cont  = { "status" : ("cont "  + filename)}


# The main event

    print("[audioOL] Entering polling loop...")
    r.xadd("audioOL", audioOL_start)

    isPlaying = True

    while h_ffplay.poll() is None:

        time.sleep(0.01)
        if curses.wrapper(main) == 32:
            if isPlaying:
                os.killpg(os.getpgid(h_ffplay.pid), signal.SIGSTOP)
                r.xadd("audioOL", audioOL_stop) #(r, "audioOL", fileName + " STOP")
            else:
                os.killpg(os.getpgid(h_ffplay.pid), signal.SIGCONT)
                r.xadd("audioOL", audioOL_cont) #(r, "audioOL", fileName + " STOP")
            isPlaying = not isPlaying

    r.xadd("audioOL", audioOL_end)
    print("[audioOL] Done!")








    # This code is required for capturing keyboard input
    # orig_settings = termios.tcgetattr(sys.stdin)
    # tty.setcbreak(sys.stdin)



    # termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)

        # sleep(1)
        # print(h_ffplay.poll())
    
    #, stdout=h_ffmpeg.stdout)

        # print(h_ffplay.poll())
        # x = sys.stdin.read(1)[0]
        # if x == ' ':
        #     if isPlaying:
        #         os.killpg(os.getpgid(h_ffplay.pid), signal.SIGSTOP)
        #         publish(r, "audioOL", fileName + " STOP")
        #     else:
        #         os.killpg(os.getpgid(h_ffplay.pid), signal.SIGCONT)
        #         publish(r, "audioOL", fileName + " CONT")
        #     isPlaying = not isPlaying

        # with Input(keynames='curses') as input_generator:
        #     for e in input_generator:
