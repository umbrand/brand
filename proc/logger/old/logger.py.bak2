# Logger.py
# This function makes multiple connections to various Redis databases and subscribes to variables of interest
# It then contains the logic it needs to parse it nicely into a table
#
# David Brandman, April 2020
#
#
# Each process is designed to have its own Redis server, with its own IP and port.
# IPC occurs with a process publishing its available data.
# The point of the Logger is to capture all of the published data in one place
# It's designed so that there is one Class -- Listener -- which contains the important
# information for connecting to a Redis server and for handling a sqlite3 connection
#
# Because I can't write to SQLite in threads, I needed to implement a queuing system to get things to work.
# It's a bit convoluted, but:
#
# 1) There is a listener object for each of the different Redis server I want to listen to
# 2) Each listener object gets its own queue
# 3) Each listener object listens and has its own callback. It launches the callback when a message is published
# 4) Each callback creates a string that is the SQL message to execute
# 5) Each thread then sends the message down the queue, which is then executed
#
# audio OL object --> callback after published message --> queue ---
#                                                                   |--> combined queue --> executes command
# rawData object  --> callback after published message --> queue ---
#
# Hence, a thread for each object, and then each object has a handleFunction that is handleded in a thread.
# The advantage of this approach is that each process now how its own listener objects, which compartimentalizes
# things nicely. There are more efficient ways this could have been done; for example, by having each
# listener have its own :memory: database and then copying the tables as part of the write step.
# However, I think this approach is easiest for iterating, since in order to listen to a new variable
#
# To listen to a new variable, you need to do three things:
# 1) Decide if you need a new table when the Listener is declared
# 2) Tell the Redis pipe to subscribe to a new variable name
# 3) Define the handler for that variable name
#
#
# TODO: Sqlite3 has multiple thread modes. The default enfoced by python wrapper
# is to disallow writing to database through thread other than the one used
# to make connection. The alternative it sot set the check_same_thread clause in the
# connection to make it so taht multiple threads can write. If this logger
# turns out to be too slow, then it's worth looking into
# It also turns out that multiple connections can happen to a single
# in memory database, https://sqlite.org/inmemorydb.html
# 


import sqlite3
from sqlite3 import Error
import redis
import time
import threading
import queue


##########################################
## Helper function for working with SQL
##########################################
def sqlConnect():
    try:
        con = sqlite3.connect(':memory:')
    except Error:
        print(Error)
    finally:
        return con

##########################################
## Base listener class
##########################################

class Listener:
    def __init__(self, name, con, queue, redisIP='127.0.0.1', redisPort=6379):

        self.redisIP   = redisIP
        self.redisPort = redisPort
        self.name      = name
        self.r         = redis.Redis(host = redisIP, port = redisPort, db = 0)
        self.con       = con # Con here refers to the sqlite3 con
        self.queue     = queue
        self.p         = self.r.pubsub()

    def listenAndParse(self):

        for m in self.p.listen(): # Blocks here. Each listener has its own subscriptions
            pass

    def display(self, val):
        print("[logger][%s] %s" % (self.name, val))

##########################################
## Listener for RawData
##########################################

class ListenerRawData(Listener):
    def __init__(self, con, queue, redisIP, redisPort):

        Listener.__init__(self, 'rawData', con, queue, redisIP, redisPort)
        con.execute("CREATE TABLE if not exists rawData(timestamp TEXT, value TEXT)")

        self.p.subscribe(**{'rawData'    : self.handlerRawData})

    def handlerRawData(self, msg):
        data = msg['data'].decode('utf-8').split(",", 1)
        sqlStr = "INSERT INTO rawData values ('%s', '%s')" % tuple(data)
        self.queue.put(sqlStr)

##########################################
## Listener for audioOL
##########################################

class ListenerAudioOL(Listener):
    def __init__(self, con, queue, redisIP, redisPort):

        Listener.__init__(self, 'audioOL', con, queue, redisIP, redisPort)
        con.execute("CREATE TABLE if not exists audioOL(timestamp TEXT, value TEXT)")

        self.p.subscribe(**{'audioOL' : self.handlerSoundStatus})

    def handlerSoundStatus(self, msg):
        data = msg['data'].decode('utf-8').split(",", 1)
        sqlStr = "INSERT INTO audioOL values ('%s', '%s')" % tuple(data)
        self.queue.put(sqlStr)


##########################################
## Write database to disk
##########################################

def writeDatabaseToDisk(con):

    # def progress(status, remaining, total):
    #     print(f'Copied {total-remaining} of {total} pages...')

    print("Backing up")

    bck = sqlite3.connect('backup.db')
    with bck:
        con.backup(bck, pages=0) #, progress = progress)

    bck.close()

def backupTimer(queue):
    while True:
        time.sleep(1)
        queue.put(1)


##########################################
## Main event
##########################################

if __name__ == '__main__':
    con = sqlConnect()

    rawDataQueue  = queue.Queue(maxsize = 0)
    audioOLQueue  = queue.Queue(maxsize = 0)
    combinedQueue = queue.Queue(maxsize = 0)
    backupQueue   = queue.Queue(maxsize = 0)
    
    def listen_and_forward(queue):
        while True:
            combinedQueue.put((queue, queue.get()))

    l1 = ListenerRawData(con,rawDataQueue, redisIP='127.0.0.1', redisPort=6379)
    l2 = ListenerAudioOL(con,audioOLQueue, redisIP='127.0.0.1', redisPort=6000)

    threading.Thread(target=l1.listenAndParse).start()
    threading.Thread(target=l2.listenAndParse).start()
    threading.Thread(target=lambda: backupTimer(backupQueue)).start()

    t = threading.Thread(target=listen_and_forward, args=(rawDataQueue,))
    t.daemon = True
    t.start()
    t = threading.Thread(target=listen_and_forward, args=(audioOLQueue,))
    t.daemon = True
    t.start()


    while True:
        which, message = combinedQueue.get()
        con.execute(message)

        if not backupQueue.empty():
            con.commit()
            writeDatabaseToDisk(con)
            backupQueue.queue.clear()










        # print('---------Raw Data----------')
        # for row in con.execute("select * from rawData"):
        #     print(row)

        # print('---------AUDIOOOL----------')
        # for row in con.execute("select * from audioOL"):
        #     print(row)





    # def handlerSoundSTOP(self, msg):
    #     data = msg['data'].decode('utf-8').split(",", 1)
    #     sqlStr = "INSERT INTO audioOL values ('%s', '%s')" % tuple(data)
    #     self.queue.put(sqlStr)
