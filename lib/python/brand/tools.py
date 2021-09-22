import redis
import yaml


def get_parameter_value(fileName, field):
    """
    Get the parameter specified by 'field' from a file

    Parameters
    ----------
    fileName : str
        Path of the YAML file
    field : str
        Name of the parameter to be loaded

    Returns
    -------
    object
        Value of the parameter
    """
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


def get_node_parameter_value(fileName, node, field):
    """
    Get the parameter specified by 'field' from the 'node' in a file

    Parameters
    ----------
    fileName : str
        Path of the YAML file
    node : str
        Name of the node to use
    field : str
        Name of the parameter to be loaded

    Returns
    -------
    object
        Value of the parameter
    """
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for node_list in yamlData['Nodes']:
        if node_list['Name'] == node:
            return node_list['Parameters'][field]


def initializeRedisFromYAML(fileName, processName=None):
    """
    Create a redis.Redis object according to the configuration in a YAML file

    Parameters
    ----------
    fileName : str
        Path of the YAML file
    processName : str, optional
        Name of the process that is calling this function, by default None

    Returns
    -------
    redis.Redis
        Instance of the redis.Redis class
    """
    pname = f"[{processName}] " if processName is not None else ""
    print(f"{pname}connecting to Redis using: {fileName}")

    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    redis_params = yamlData['RedisConnection']['Parameters']
    # connect to redis, figure out the streams of interest
    if ('redis_realtime_socket' in redis_params
            and redis_params['redis_realtime_socket'] is not None):
        redis_socket = redis_params['redis_realtime_socket']
        print(f'Redis Socket Path {redis_socket}')
        r = redis.Redis(unix_socket_path=redis_socket)
    else:
        redis_ip = redis_params['redis_realtime_ip']
        redis_port = redis_params['redis_realtime_port']
        print(f'Redis IP: {redis_ip}, Redis port: {redis_port}')
        r = redis.Redis(host=redis_ip, port=redis_port)

    print(f"{pname}Initialized Redis")

    return r
