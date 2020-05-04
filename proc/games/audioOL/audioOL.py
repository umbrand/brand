

import subprocess
import redis
import ffmpeg
import time
import sys
import signal
import os
import curses

sys.path.insert(1, '../../../lib/')
from redisTools import *


# https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
# https://stackoverflow.com/questions/34497323/what-is-the-easiest-way-to-detect-key-presses-in-python-3-on-a-linux-machine


def main(stdscr):
    """checking for keypress"""
    stdscr.nodelay(True)  # do not wait for input when calling getch
    return stdscr.getch()

if __name__ == "__main__":

    r = initializeRedisFromYAML('audioOL')
    fileName = getString(r, "fileName")

    ffplayString = ["ffplay" \
            , "-autoexit -nodisp -hide_banner -loglevel panic" \
            , fileName]

    ffplayString = " ".join(ffplayString)
    print("[AudioOL] Executing: ", ffplayString)

    # Launch the subprocess ffplay for playing the sound
    h_ffplay = subprocess.Popen(ffplayString, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
    publish(r, "audioOL", fileName + " START")

    isPlaying = True
    

    while h_ffplay.poll() is None:

        time.sleep(0.01)
        if curses.wrapper(main) == 32:
            if isPlaying:
                os.killpg(os.getpgid(h_ffplay.pid), signal.SIGSTOP)
                publish(r, "audioOL", fileName + " STOP")
            else:
                os.killpg(os.getpgid(h_ffplay.pid), signal.SIGCONT)
                publish(r, "audioOL", fileName + " CONT")
            isPlaying = not isPlaying

    publish(r, "audioOL", fileName + " END")








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
