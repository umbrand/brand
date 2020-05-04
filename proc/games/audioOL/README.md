# Open Loop Audio play
### David Brandman
### Version 0.1, April 2020

This code is designed to solve the following problems:
1. We want to play a recording for someone. We need to know when the recording starts, stops, and if there are any pauses
2. We want to be able to easily configure what we're playing for someone
3. I want to know when the sound is actually presented to the person.

I took numerous iterations of this program to get something to work. The first approach was to use ffmpeg to feed out to a pipe as well as to ffplay. I assumed that the timing for both streams would be the same. This turned out to be false, despite playing with a lot of different combinations of features of ffmpeg. While I was able to get the two sound steams to synchronize with each other for LPC-based encoding, having a start/stop feature didn't work for reliably getting bytes. Let it be know when I go to design the audioCL experiment that start/stop won't be possible, even if overlays will be. At least not with ffmpeg.

The answer I came up with is simple, and not terribly elegant. Here's how this works:
1. Call the Launcher. This runs a tmux session
2. The first tmux window initializes the system
3. The first tmux window launches ffplay in the second
4. When the first detects a pause, it sents a STOP (CONT) signal to the other
5. When the ffplay is launched, closed, or when any of the signals are sent for communication, we record the time in Redis

