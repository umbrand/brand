# List of processes


## audioOL  

For playing sounds files. It creates a stream which keeps track of the state of the playback

## cerebusAdapter

Designed for moving outputs from blackrock neural signal processor to Redis. Waits on incoming UDP packets and combines multiple cerebus packets together to a single Redis write.

## finalizeRDB

Add the content of additional files to Redis when writing streams is complete

## generator

Produce step function output, broadcasted within cerebus packets on UDP

## lfads

The future home of the lfads decoder

## logger

Move data from redis to a SQL file

## lpcnet_decode

Translate encoded LPCnet packets to sound 

## lpcnet_encode

Translate sound to LPCnet packets

## monitor

Introspective monitoring of performance. Run on a timer and compute jitter / latency 

## pipe

real-time signal processing, moving raw voltage samples to extracted features (e.g. spike counts)

## replay

Take a binary file of serialized data from Blackrock neural signal processor and produce UDP packets

## timer

Send signals to processes that may be pausing 


