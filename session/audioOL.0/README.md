# audioOL 

Written by: David Brandman
Date: May 2020

## Description

The goal of this experiment is to play some audio recordings to the user. The audioOL module is designed to play a sound using ffplay. The experimenter can start/stop the recording as it's playing. The module produces a stream called audioOL, which records the state of the recording. See the README.md in that module for more details.


## Modules


1. streamUDP -- convert NSP UDP packets for recording
2. audioOL -- play the audio recording to the user
3. rest -- access real-time information
4. logger -- convert data to sqlite3
