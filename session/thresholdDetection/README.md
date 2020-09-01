# threshold detection

Kevin Bodkin
July 2020

This session was built to test modules to extract thresholds from the 30khz data stream from the server. This will likely be added to pipe in the future


Proposed workflow:
(start) -- cerebusAdapter
(main) -- thresholdExtraction 
(end) -- finalizeRDB
```
```


The `cerebusAdapter` process sits and listens to UDP packets coming from a YAML defined port (assumed to be broadcasted UDP packets). 
It then takes the payload of the packets and transfers them to Redis.

thresholdExtraction listens to SIGUSR1 timer events (planned every 1 ms for the time being) filters and looks for points below the threshold value defined in the associated .yaml file, and removes any that are under the defined "refractory" period.


The `finalizeRDB` is designed to write a few more files to Redis before shutting down
