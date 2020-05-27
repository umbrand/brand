
# Open Loop Audio play
### David Brandman
### Version 0.2, May 2020

This code is designed to play a recording for someone. We need to know when the recording starts, stops, and if there are any pauses.

# Streams

The audioOL process generates an audioOL stream. The stream has the key value "status" which is a text field, and has the following states:

status : start
status : end
status : stop
status : cont

The filename played for each of the states is then appended to the state so that it's clear exactly what's happening.

# Program design

The ability to poll keyboard input isn't pretty from python. It may even be worth rewriting this in C to get better timing. After much Googling, I came up with solutions from the following resources: 

https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
https://stackoverflow.com/questions/34497323/what-is-the-easiest-way-to-detect-key-presses-in-python-3-on-a-linux-machine

In short, we sit in a while loop and poll keyboard input. The sound is played using ffplay (since it works so nicely with any kind of auditory input...) in a subprocess.  When we get a keyboard input when send a signal to ffplay. It turns out the designers had it respond to SIGSTOP and SIGCONT (which I couldn't find documented anywhere?) but it's mighty convenient. 



## Previous notes

I took numerous iterations of this program to get something to work. The first approach was to use ffmpeg to feed out to a pipe as well as to ffplay. I assumed that the timing for both streams would be the same. This turned out to be false, despite playing with a lot of different combinations of features of ffmpeg. While I was able to get the two sound steams to synchronize with each other for LPC-based encoding, having a start/stop feature didn't work for reliably getting bytes. Let it be known when that when I go to design the audioCL experiment that start/stop won't be possible, even if overlays will be. At least not with ffmpeg.


