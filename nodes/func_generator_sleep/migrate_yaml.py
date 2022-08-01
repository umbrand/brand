# %%
import yaml

node_name = 'func_generator'

with open(f'{node_name}.yaml', 'r') as f:
    yaml_data = yaml.safe_load(f)
# %%
yaml_data


# %%
def get_parameter_value(yamlData, field):
    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


# %%
with open(
        '/home/snel/Projects/brand/graphs/sharedDevelopment/decoderTest/0.0/decoderTest.yaml',
        'r') as f:
    new_yaml_ex = yaml.safe_load(f)

# %%
new_yaml = {'RedisConnection': {'Parameters': {}}}

for param
new_yaml['RedisConnection']['Parameters'][
    'redis_realtime_ip'] = get_parameter_value(yaml_data, 'redis_ip')
new_yaml = {'Nodes': []}
node_info = {'Name': node_name, 'Version': 0.0}
node_info['Parameters'] = {
    param['name']: param['value']
    for param in yaml_data['parameters']
}
new_yaml['Nodes'].append(node_info)

# %%
yaml_data['parameters'][0]['name'], yaml_data['parameters'][0]['value']
# %%
