import logging
import signal
import sys
from datetime import datetime

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

while True:
    entry = r.xread({b'publisher': '$'}, block=0)
    entry_id, entry_dict = entry[0][1][0]
    ts = float(entry_dict[b'ts'])
    val = np.frombuffer(entry_dict[b'val'])
    r.xadd('subscriber', {
        'ts': datetime.now().timestamp(),
        'id': entry_id,
    })
