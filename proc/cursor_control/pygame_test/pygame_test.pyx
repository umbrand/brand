import sys
import pygame


pygame.init()

size = width, height = 1000, 1000
black = 0, 0, 0

screen = pygame.display.set_mode(size)

ball = pygame.image.load("./yellow_circle.png")
ball = pygame.transform.scale(ball, (50, 50))
ballrect = ball.get_rect()

while 1:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
        elif event.type == pygame.MOUSEMOTION:
            # event attributes: {pos: (x, y), rel: (x, y)}
            ballrect.x = event.pos[0] - (ballrect.w / 2)
            ballrect.y = event.pos[1] - (ballrect.h / 2)

    screen.fill(black)
    screen.blit(ball, ballrect)
    pygame.display.flip()