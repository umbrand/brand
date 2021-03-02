# behavior FSM test

Kevin Bodkin
Feb 2021

This session was built to test modules to extract thresholds from the 30khz data stream from the server. This will likely be added to pipe in the future


Proposed workflow:
(start) -- cerebusAdapter 
(main) -- behaviorFSM.py monitor cursor_control
(end) -- finalizeRDB
```
```


The `cerebusAdapter` process sits and listens to UDP packets coming from a YAML defined port (assumed to be broadcasted UDP packets). 
It then takes the payload of the packets and transfers them to Redis.

behaviorFSM brings in 1khz signals from the Redis and uses them as a cursor to perform a task. The targets and the gain fromthe sensors to the cursor are defined in an associated .yaml file it outputs the status of the task, cursor and target locations to Redis to be used by the cursor_control script

cursor_control displays the cursor and the target. Might need a better name than that, tbh


The `finalizeRDB` is designed to write a few more files to Redis before shutting down
