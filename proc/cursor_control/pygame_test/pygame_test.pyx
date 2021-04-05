import os
import sys
import pygame
import pygame.freetype

os.environ["SDL_VIDEODRIVER"] = ""

pygame.init()
GAME_FONT = pygame.freetype.SysFont(pygame.font.get_default_font(), 24)

size = width, height = 1000, 1000
black = 0, 0, 0

display_flags = pygame.DOUBLEBUF | pygame.HWSURFACE
screen = pygame.display.set_mode(size, flags=display_flags, vsync=1)

ball = pygame.image.load("./yellow_circle.png")
ball = pygame.transform.scale(ball, (50, 50))
ballrect = ball.get_rect()

clock = pygame.time.Clock()

while 1:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
        elif event.type == pygame.MOUSEMOTION:
            # event attributes: {pos: (x, y), rel: (x, y)}
            ballrect.x = event.pos[0] - (ballrect.w / 2)
            ballrect.y = event.pos[1] - (ballrect.h / 2)

    screen.fill(black)
    GAME_FONT.render_to(screen, (40, 350),
                        f'{clock.get_fps() :.2f}', (255, 255, 255),
                        size=64)
    screen.blit(ball, ballrect)
    pygame.display.flip()
    clock.tick(300)
