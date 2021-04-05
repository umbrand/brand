# nidaq_acquisition

Takes data from any nidaq system that can interact with daqmx and inputs it into the Redis stream
according to the associated yaml settings file.



## Required dependencies
The system needs to have daqmx, hiredis, and redistools in place. That last one is specifically
for the rt rig system, and is just a couple of handler functions that make life a little easier.
