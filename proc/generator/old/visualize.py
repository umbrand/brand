
## Imports
import socket
import redis
import numpy as np
import multiprocessing
import pandas as pd
import matplotlib.pyplot as plt
import os
import multiprocessing
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
import time
from matplotlib.animation import FuncAnimation, TimedAnimation


r = redis.Redis()

def updatePlot(i):

    redisData = r.lrange("rawData", 0, 1000)
    allChannels = [np.fromiter(x.split(), dtype='int16') for x in redisData]

    chan = 0
    y = np.flip([x[chan] for x in allChannels])

    y = y * 0.029 # Voltage correction

    plt.cla()
    plt.scatter(x=np.arange(0,len(y)),y=y, s=3)
    plt.ylim((-200,200))
    # plt.ylim((0,2000))


def move():
    mngr = plt.get_current_fig_manager()
    mngr.window.setGeometry(1000,100,640, 545)

if __name__ == '__main__':

    fig, ax = plt.subplots()
    ani = FuncAnimation(plt.gcf(), updatePlot, interval=100)
    plt.show()
    move()






    # hUpdatePlot = scheduler.add_job(lambda: updatePlot(line), 'interval', seconds = 1)
    
    # p = multiprocessing.Process(target=receivePackets)
    # p.start()

    # print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))
    # try:
    #     scheduler.start()
    # except (KeyboardInterrupt, SystemExit):
    #     pass

    # plt.show(block=False)

#     line, = ax.plot(np.arange(0,47))
#     plt.show(block=False)
#     plt.ion()


    # pipe =  r.pipeline()
    # pipe.multi()
    # pipe.lrange("rawData", 0, 47)
    # # pipe.ltrim("rawData", 0, 47)
    # newData = pipe.execute()
    # y = (np.array(newData[0], dtype='int16'))
# def receivePackets():
#     try:
#         data, addr = sock.recvfrom(20000)
#     except BlockingIOError:
#         print("no data")
#         return

#     a = np.frombuffer(data, dtype='int16').tolist()
#     r.lpush("rawData", *a)
#     r.ltrim("rawData", 0, 48*1000)
#     print( "received message length:", len(data))
# UDP_IP = "127.0.0.1"
# UDP_PORT = 53000

# sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
# sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# sock.bind(("", UDP_PORT))
# sock.setblocking(0)
    # data, addr = sock.recvfrom(20000)
    # rawData = np.frombuffer(data, dtype='int16').tolist()
    # print(len(rawData))


    # job_defaults = {
    #     'coalesce': False,
    #     'max_instances': 2
    # }

    # scheduler   = BlockingScheduler()
    # scheduler = BackgroundScheduler(job_defaults=job_defaults)
    # hReceivePackets = scheduler.add_job(receivePackets, 'interval', seconds=0.01)
    # scheduler.start()
