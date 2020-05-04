# Logger.py
# This function makes multiple connections to various Redis databases and subscribes to variables of interest
# It then contains the logic it needs to parse it nicely into a table

import sqlite3
from sqlite3 import Error
import redis

import sys
sys.path.insert(1, '../../lib/')
from redisTools import *


if __name__ == '__main__':
    r = redis.Redis()
    publish(r, "rawData", "1 1 1 1 1 1 1 1")
    
    

# def sql_connection():
#     try:
#         con = sqlite3.connect(':memory:')
#     except Error:
#         print(Error)
#     finally:
#         return con

# def sql_CreateTable(con):
#     con.execute("
#     # cursorObj = con.cursor()
#     # cursorObj.execute("CREATE TABLE papers(id integer PRIMARY KEY, md5sum text, fileName text, doi text, bibtex text)")
#     # con.commit()

