import pyglet
import time
import numpy as np

window = pyglet.window.Window(width=1000, height=1000)

label = pyglet.text.Label('Hello, world',
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


@window.event
def on_mouse_motion(x, y, dx, dy):
    mouse_data['x'] = x
    mouse_data['y'] = y


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