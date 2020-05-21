# Logger.py
# When we're done with our session, we want to summarize data from multiple sources

import sqlite3
from sqlite3 import Error
import redis
import time
import datetime
import yaml
import sys

# Pathway to get redisTools.py
sys.path.insert(1, '../../lib/redisTools/')
from redisTools import getSingleValue

YAML_FILE = "logger.yaml"

##########################################
## Helper function for working with SQL
##########################################
def sql_connect(filename):

    datetime_string = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H.%M.%S')
    sql_filename = filename + "." + datetime_string + ".sqlite3"

    try:
        con = sqlite3.connect(sql_filename)
    except Error:
        print(Error)
    finally:
        return con

##########################################
## Helper function for working with Redis
##########################################
def redis_connect():

    redis_ip = getSingleValue(YAML_FILE,"redis_ip")
    redis_port = getSingleValue(YAML_FILE,"redis_port")
    print("[logger] Initializing Redis with IP :" , redis_ip, ", port: ", redis_port)
    r = redis.Redis(host = redis_ip, port = redis_port, db = 0)
    return r


##########################################
## Helper function for working with yaml
##########################################
def load_process_log_yaml(process):
    try:
        filename = "yaml/" + process + "_log.yaml"
        with open(filename, 'r') as f:
            yaml_data = yaml.safe_load(f)

    except IOError:
        return ""

    return yaml_data


##########################################
## stream_to_sql
##########################################
def stream_to_sql(con, process_name, stream_list):

    for stream in stream_list:

        col_names = [(x['key'] + " " + x['type']) for x in stream['data']]
        col_names = ",".join(col_names)
        col_names = "(id text," + col_names + ")"
        sqlStr = "CREATE TABLE IF NOT EXISTS %s %s" % (stream['table_name'], col_names)

        print("[logger] Creating table: " , stream['table_name'])
        con.execute(sqlStr)

        print("[logger] Loading data into: " , stream['table_name'])

        data_list = r.xrange(stream['stream_key'])
        for data in data_list:
            vals = [data[0].decode('utf-8')]
            vals += [value.decode('utf-8') for value in data[1].values()]
            # vals = ",".join(vals)
            # vals = "(" + id + "," + vals + ")"

            cols = ["?"] * (len(vals))
            cols = ",".join(cols)
            cols = "(" + cols + ")"

            sqlStr = "INSERT INTO %s values %s" % (stream['table_name'], cols)
            con.execute(sqlStr, tuple(vals))
            con.commit()




##########################################
## stream_to_sql
##########################################
def file_to_sql(con, process_name, file_list):

    for file in file_list:

        print("[logger] Creating table: " , file['table_name'])
            
        sqlStr = "CREATE TABLE IF NOT EXISTS %s (value TEXT)" % (file['table_name'])
        con.execute(sqlStr)

        file_path = "../" + process_name + "/" + file['file_name']

        print("[logger] Reading file: " , file_path)
        file_fd = open(file_path, "r") 
        file_contents = file_fd.read() 

        print("[logger] Inserting data from: " , file_path)
        sqlStr = "INSERT INTO %s values (?)" % (file['table_name'])
        con.execute(sqlStr, (file_contents,))

        con.commit()


##########################################
## Main event
##########################################

if __name__ == "__main__":

    r            = redis_connect()
    sql_filename = getSingleValue(YAML_FILE,"filename")
    con          = sql_connect(sql_filename)

# Start by getting a list of the process_list that we want to convert to a SQL table
# Then go through each process, and check to see if it logger.py knows how to handle
# The type of data it's presented with

    process_list = getSingleValue(YAML_FILE,"process_list")

    for process_name in process_list:

        yaml_data = load_process_log_yaml(process_name)

        if "stream" in yaml_data:
            stream_to_sql(con, process_name, yaml_data['stream'])

        if "file" in yaml_data:
            file_to_sql(con, process_name, yaml_data['file'])
