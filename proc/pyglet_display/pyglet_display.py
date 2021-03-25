import signal
import sys
import time

import numpy as np
import pyglet
import redis
import yaml

window = pyglet.window.Window(width=1000, height=1000, fullscreen=True)

label = pyglet.text.Label('',
                          font_name=['Noto Sans', 'Times New Roman'],
                          font_size=36,
                          x=0,
                          y=window.height,
                          anchor_x='left',
                          anchor_y='top',
                          color=(125, 125, 125, 255))

mouse_data = {'x': 0, 'y': 0}

RED = (255, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)

pointer = pyglet.shapes.Circle(x=0, y=0, radius=50, color=YELLOW)
target = pyglet.shapes.Rectangle(x=500,
                                 y=500,
                                 width=100,
                                 height=100,
                                 color=RED)

# hiding mouse
window.set_mouse_visible(False)

# @window.event
# def on_mouse_motion(x, y, dx, dy):
#     mouse_data['x'] = x
#     mouse_data['y'] = y

YAML_FILE = "pyglet_display.yaml"
PROCESS = "pyglet_display"

def get_parameter_value(fileName, field):
    with open(fileName, 'r') as f:
        yamlData = yaml.safe_load(f)

    for record in yamlData['parameters']:
        if record['name'] == field:
            return record['value']

redis_ip = get_parameter_value(YAML_FILE, "redis_ip")
redis_port = get_parameter_value(YAML_FILE, "redis_port")
print(f"[{PROCESS :s}] Initializing Redis with IP : {redis_ip :s}, "
    f"port: {redis_port :d}")
rdb = redis.Redis(host=redis_ip, port=redis_port, db=0)

def get_mouse_position():
    reply = rdb.xread(streams={'cursorData': '$'}, count=1, block=0)
    entry_dict = reply[0][1][0][1]
    mouse_data = dict(x=int(entry_dict[b'dx']), y=-int(entry_dict[b'dy']))
    return mouse_data

def signal_handler(sig, frame):
    print(f"[{PROCESS :s}] SIGINT received. Shutting down.")
    pyglet.app.exit()
    rdb.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

last_time = time.time()
i = 0
refresh_rate = 0


@window.event
def draw_stuff(*args):
    global last_time
    global current_time
    global i
    if i > 99:
        current_time = time.time()
        refresh_rate = 100 / (current_time - last_time)
        last_time = current_time
        label.text = f'{refresh_rate}'
        i = 0

    mouse_data = get_mouse_position()

    pointer.x = mouse_data['x']
    pointer.y = mouse_data['y']
    window.clear()

    # calculate distance between pointer center and target center
    xdist = np.abs(target.x + 50 - pointer.x)
    ydist = np.abs(target.y + 50 - pointer.y)

    if xdist <= 100 and ydist <= 100:
        target.color = GREEN
    else:
        target.color = RED

    target.draw()
    pointer.draw()
    # label.draw()

    i += 1


pyglet.clock.schedule(draw_stuff)

pyglet.app.run()
