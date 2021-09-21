# Usage

Set up the environment
```bash
$ source setup.sh
```

List available graph locations
```bash
$ createGraph
Please specify a location
Current locations are:  sharedDevelopment
```

Create a graph from the [template](../graphs/templateLocation/templateGraph/0.0/templateGraph.yaml) and store it in `graphs/sharedDevelopment`
```bash
$ createGraph sharedDevelopment mygraph
$ ls graphs/sharedDevelopment/
mygraph
```

Create a load script for your graph
```bash
$ touch ./graphs/sharedDevelopment/mygraph/0.0/load.sh
$ chmod +x ./graphs/sharedDevelopment/mygraph/0.0/load.sh
```

Create a run script for your graph
```bash
$ touch ./graphs/sharedDevelopment/mygraph/0.0/run.sh
$ chmod +x ./graphs/sharedDevelopment/mygraph/0.0/run.sh
```

Fill in the load script with functions that will copy your graph to the run folder.

Fill in the run script with commands that will start the nodes needed to run your graph.

Load your graph
```bash
$ load sharedDevelopment/decoderTest/0.0
```
Run your graph
```bash
$ run
```
