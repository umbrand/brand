import argparse
import json
import time

import redis
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('-d',
                    '--duration',
                    required=False,
                    type=int,
                    help="time (seconds) to wait before stopping the graph")
parser.add_argument("-g",
                    "--graph",
                    default='testGraph.yaml',
                    required=False,
                    help="path to graph file")
args = parser.parse_args()

with open(args.graph, 'r') as f:
    graph = yaml.safe_load(f)

r = redis.Redis()

print(f'Starting graph from {args.graph}')
r.xadd('supervisor_ipstream', {
    'commands': 'startGraph',
    'graph': json.dumps(graph)
})

if args.duration:
    print(f'Waiting {args.duration} seconds')
    time.sleep(args.duration)
else:
    input('Hit ENTER to stop graph...')

print('Stopping graph')
r.xadd('supervisor_ipstream', {'commands': 'stopGraph'})
