import socket
import struct
import redis
import numpy as np

UDP_IP = "127.0.0.1"
UDP_PORT = 53000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.bind(("", UDP_PORT))


r = redis.Redis()

while True:
    data, addr = sock.recvfrom(20000)
    a = np.frombuffer(data, dtype='int16').tolist()
    # r.lpush("rawData", *a)
    # print( "received message length:", len(data))
    print(a)
