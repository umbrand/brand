import logging
import signal
import sys
import time

import numpy as np
import yaml
from redis import Redis

YAML_FILE = 'subscriber.yaml'

logging.basicConfig(format='%(levelname)s:subscriber:%(message)s',
                    level=logging.INFO)


def get_parameter_value(fileName, field):
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


# setting up clean exit code
def signal_handler(sig, frame):  # setup the clean exit code with a warning
    logging.info('SIGINT received, Exiting')
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

redis_ip = get_parameter_value(YAML_FILE, 'redis_ip')
redis_port = get_parameter_value(YAML_FILE, 'redis_port')

r = Redis(host=redis_ip, port=redis_port)

entry_id = '$'
while True:
    entry = r.xread({b'publisher': entry_id}, block=0)
    entry_id, entry_dict = entry[0][1][0]
    r.xadd('subscriber', {
        'ts': time.perf_counter(),
        'ts_sent': float(entry_dict[b'ts']),
        'size': int(entry_dict[b'size']),
        'counter': int(entry_dict[b'counter'])
    })
