# threshold detection

Kevin Bodkin
February 2021

Testing the nidaq inputs

Proposed workflow:
(start) -- cerebusAdapter
(main) -- nidaq_acquisition 
(end) -- finalizeRDB
```
```


nidaq_acquisition polls the connected nidaq card for data and puts it into the redis stream.

The `finalizeRDB` is designed to write a few more files to Redis before shutting down
