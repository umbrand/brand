import os
import sys
import signal
import pygame
from multiprocessing import Process
import redis
import yaml

REFRESH_RATE = 60
YAML_FILE = "pycursor_control.yaml"
PROCESS = "pycursor_control"

def mouse_subscriber_thread():
    redis_ip = get_parameter_value(YAML_FILE, "redis_ip")
    redis_port = get_parameter_value(YAML_FILE, "redis_port")
    print(f"[{PROCESS :s}] Initializing Redis with IP : {redis_ip :s}, "
        f"port: {redis_port :d}")
    rdb = redis.Redis(host=redis_ip, port=redis_port, db=0)
    while True:
        reply = redis.xread(streams={'mouseData': '$'}, count=None, block=0)
        print(reply)
        break


def get_parameter_value(fileName, field):
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']


def signal_handler(sig, frame):
    print(f"[{PROCESS :s}] SIGINT received. Shutting down.")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    # redis
    redis_ip = get_parameter_value(YAML_FILE, "redis_ip")
    redis_port = get_parameter_value(YAML_FILE, "redis_port")
    print(f"[{PROCESS :s}] Initializing Redis with IP : {redis_ip :s}, "
        f"port: {redis_port :d}")
    rdb = redis.Redis(host=redis_ip, port=redis_port, db=0)

    mouse_motion = [0, 0]

    # pygame
    pygame.init()

    size = width, height = 1000, 1000
    black = (0, 0, 0)

    flags = 0 # pygame.OPENGL
    screen = pygame.display.set_mode(size, flags, vsync=1)

    ball = pygame.image.load("./yellow_circle.png")
    ball = pygame.transform.scale(ball, (50, 50))
    ballrect = ball.get_rect()

    origin = (int((width - ballrect.w) / 2), int((height - ballrect.h) / 2))
    ballrect.x, ballrect.y = origin
    pygame.mouse.set_pos(origin)

    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)

        reply = rdb.xread(streams={'mouseData': '$'}, count=None, block=0)
        rdict = reply[0][1][0][1]

        # print(rdict)
        ballrect.x += int(rdict[b'dx'])
        ballrect.y += int(rdict[b'dy'])

        screen.fill(black)
        screen.blit(ball, ballrect)
        pygame.display.flip()
        clock.tick(REFRESH_RATE)