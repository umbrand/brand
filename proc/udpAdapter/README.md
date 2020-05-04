# Reading UDP packets and pushing them to Redis

David Brandman, 2 April 2020

After a few iterations, I realized that Python was rather slow when it needed to sit and wait on sockets and subsequently do something afterwards. So I wrote a utility that listens to broadcasting data (i.e. something like Cerebrus packets) and then pushes them to a Redis database.

The redis code is located in the lib/ directory.

The code is fairly straightforward. Sit in a while loop and block on a port, and when you get data convert the data to strings and then push it to Redis. We expec the data to come out in Row format; that is, one timestep has all of the data for all of the channels. That's exactly how it's pushed to Redis
