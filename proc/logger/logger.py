# Logger.py
# When we're done with our session, we want to summarize data from multiple sources

# Sqlite3 types:

# NULL. The value is a NULL value.
# INTEGER. The value is a signed integer, stored in 1, 2, 3, 4, 6, or 8 bytes
# REAL. The value is a floating point value, stored as an 8-byte IEEE floating point number.
# TEXT. The value is a text string, stored using the database encoding (UTF-8, UTF-16BE or UTF-16LE).
# BLOB. The value is a blob of data, stored exactly as it was input.



import sqlite3
from sqlite3 import Error
import redis
import time
import datetime
import yaml
import sys

# Pathway to get redisTools.py
sys.path.insert(1, '../lib/redisTools/')
from redisTools import get_parameter_value

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

    redis_ip   = get_parameter_value(YAML_FILE,"redis_ip")
    redis_port = get_parameter_value(YAML_FILE,"redis_port")

    print("[logger] Initializing Redis with IP :" , redis_ip, ", port: ", redis_port)
    r = redis.Redis(host = redis_ip, port = redis_port, db = 0)
    return r


##########################################
## Helper function for working with yaml
##########################################
def load_yaml():
    try:
        with open(YAML_FILE, 'r') as f:
            yaml_data = yaml.safe_load(f)

    except IOError:
        print("[logger] Could not load logger.yaml")
        os.exit(1)

    return yaml_data


##########################################
## stream_to_sql
##########################################

#######################################################
# This segment of code is a little confusing, because of the number of layers of nested
# source of informations, and needing to cross-reference YAML with Redis streams
# yaml_stream_list is directly from the YAML file. YAML-defined streams have the following format:

# - stream_key: cerebusAdapter
#   table_name: cerebusAdapter
#   data:
#    - key: stream_key
#      type: sqlite3 type

# So we go through each of the different streams we want to move to SQL
# Next we construct a table
# Then we load pagination_number of entries from Redis, and then
# for each of the keys defined in YAML, populate a sql_row variable
# This sql_row is ultimately what will enter into sql.

def streams_to_sql(con, r, yaml_stream_list): 

    for yaml_stream in yaml_stream_list:


# Does the yaml_stream exist?

        if r.exists(yaml_stream['stream_key']) == 0:
            print("[logger] Could not find stream key ", yaml_stream['stream_key'])
            continue

# Begin by building the SQL table. The table name is the same
# as the yaml_stream. The columns are the (key type) list in the dictionary
# the final text is:
# CREATE TABLE IF NOT EXISTS [TABLE] (id text, key type, key type, ...)

        col_names = [(x['key'] + " " + x['type']) for x in yaml_stream['data']]
        col_names = ",".join(col_names)
        col_names = "(id text," + col_names + ")"
        sqlStr = "CREATE TABLE IF NOT EXISTS %s %s" % (yaml_stream['table_name'], col_names)
        print("[logger] Creating table: " , yaml_stream['table_name'])
        con.execute(sqlStr)

# Now the table has been created, we start loading data into it
# Since the streams are potentially very big we're going to
# need some pagination. 

        pagination_number = 1000

        total_entries = r.xinfo_stream(yaml_stream['stream_key'])['length']
        print("[logger] Stream " , yaml_stream['stream_key'] , "has", total_entries, "entries")


#entries_read : keep track of how many entries have been read from the yaml_stream
# xrange_output is the output of Redis. It has the following form:
# xrange_output[0] : ID
# xrange_output[1] : {key, value}
# We are going to be generating a sql_row that will be inserted using INSERT INTO ...
# ID --> data[0] 
# The instructions here (https://redis.io/commands/xrange) recommend the strategy of
# runing xrange from incrementing the -0 part, since xrange returns closed sets of data

        entries_read = 0
        id_start = r.xinfo_stream(yaml_stream['stream_key'])['first-entry'][0]

        while entries_read < total_entries:
            xrange_output = r.xrange(yaml_stream['stream_key'],min=id_start, max='+', count=pagination_number)
            entries_read += len(xrange_output)

            print("[logger] Loaded {} of {}".format(entries_read, total_entries))


            for xrange_single_output in xrange_output:

                sql_row = [xrange_single_output[0].decode('utf-8')]

                for single_yaml_stream in yaml_stream['data']:

                    raw_data = xrange_single_output[1][single_yaml_stream['key'].encode('utf-8')]

                    if single_yaml_stream['type'] != 'BLOB':
                        raw_data = raw_data.decode('utf-8')

                    sql_row += [raw_data]

                cols = ["?"] * (len(yaml_stream['data']) + 1)
                cols = ",".join(cols)
                cols = "(" + cols + ")"


                sqlStr = "INSERT INTO %s values %s" % (yaml_stream['table_name'], cols)
                con.execute(sqlStr, tuple(sql_row))
            con.commit()

            split_last_id = xrange_output[-1][0].split(b'-')
            id_start = split_last_id[0].decode('utf-8') + "-" + str(int(split_last_id[1])+1)




##########################################
## stream_to_sql
##########################################
def files_to_sql(con, table_list):

    for table in table_list:

        print("[logger] Creating table: " , table['table_name'])
            
        sqlStr = "CREATE TABLE IF NOT EXISTS %s (name TEXT, value TEXT)" % (table['table_name'])
        con.execute(sqlStr)

        for filename in table['files']:

            print("[logger] Adding file: " , filename, " to table: ", table['table_name'])
            file_fd = open(filename, "r") 
            file_contents = file_fd.read() 

            sqlStr = "INSERT INTO %s values (?,?)" % (table['table_name'])
            con.execute(sqlStr, (filename, file_contents,))

        con.commit()


##########################################
## Main event
##########################################

if __name__ == "__main__":

    r            = redis_connect()
    sql_filename = get_parameter_value(YAML_FILE,"filename")
    con          = sql_connect(sql_filename)

    yaml_data = load_yaml()
    
    streams_to_sql(con, r, yaml_data['streams'])

    files_to_sql(con, yaml_data['files'])

