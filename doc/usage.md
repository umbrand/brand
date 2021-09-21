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

