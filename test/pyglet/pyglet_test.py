import pyglet
import time

window = pyglet.window.Window(width=1000, height=1000)

label = pyglet.text.Label('Hello, world',
                          font_name=['Noto Sans', 'Times New Roman'],
                          font_size=36,
                          x=0,
                          y=window.height,
                          anchor_x='left',
                          anchor_y='top',
                          color=(125, 125, 125, 255))

image = pyglet.resource.image('circle.png')

mouse_data = {'x': 0, 'y': 0}

fps_display = pyglet.window.FPSDisplay(window)


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
    window.clear()
    label.draw()
    image.blit(x=mouse_data['x'] - image.width / 2,
               y=mouse_data['y'] - image.height / 2)
    fps_display.draw()
    i += 1


pyglet.clock.schedule(draw_stuff)

pyglet.app.run()