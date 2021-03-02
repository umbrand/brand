# Cerebus Test

David Brandman
June 2020

This session was built to begin testing how the rig could handle 30Khz data from 96 channels coming from a Cerebus device. 
It's meant for debugging and not meant to be used in production.

There are two potential workflows:
```
start=(generator/replay cerebusAdapter)
main=(monitor timer)
end=(finalizeRDB)
```

OR

```
start=(cerebusAdapter)
main=(monitor timer)
end=(finalizeRDB)
```

The first allows for the replay of either a step function (generator) or previously captured pcap data (replay). The second is what you would use
if you were running the system using a physical NSP and wanted to quantify performance.

The `cerebusAdapter` process sits and listens to UDP packets coming from a YAML defined port (assumed to be broadcasted UDP packets). 
It then takes the payload of the packets and transfers them to Redis.

The `monitor` is designed to listen to a SIGUSR1 from `timer` and then to look at the inter-call interval as well as the current
cerebus packet timestamp. It's good for assessing latency and jitter in the system.

The `finalizeRDB` is designed to write a few more files to Redis before shutting down
