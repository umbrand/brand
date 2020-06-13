# Cerebus Test

David Brandman, June 2020

This session was built to begin testing how the rig could handle 30Khz data from 96 channels coming from a Cerebus device. It's meant for debugging and not meant to be used in production.

The `cerebusAdapter` process sits and listens to UDP packets coming from a YAML defined port (assumed to be broadcasted UDP packets). It then takes the payload of the packets and transfers them to Redis.


