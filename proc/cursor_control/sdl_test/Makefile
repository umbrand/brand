PROJECT=main

ROOT ?= ../..

CC = gcc
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS)
SDL2FLAGS=$(shell pkg-config sdl2 --cflags --libs) -lSDL2_image

LINKS= 
LDPATH = 
LDFLAGS = 

CINCLUDE = 


CFILES = 

TARGET=./$(PROJECT)

all: main

main: main.c
	$(CC) $(CFLAGS) $(CINCLUDE) $(LINKS) main.c -pthread $(CFILES) $(LDPATH) -o $(TARGET) $(LDFLAGS) ${SDL2FLAGS}

clean:
	$(RM) $(TARGET)
