PROJECT=sdl_test

ROOT ?= ../..

CC = gcc
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS)
SDL2FLAGS=$(shell pkg-config sdl2 --cflags --libs) -lSDL2_image -lSDL2_ttf

LINKS= 
LDPATH = 
LDFLAGS = 

CINCLUDE = 


CFILES = 

TARGET=./$(PROJECT)

all: sdl_test

sdl_test: sdl_test.c
	$(CC) $(CFLAGS) $(CINCLUDE) $(LINKS) sdl_test.c -pthread $(CFILES) $(LDPATH) -o $(TARGET) $(LDFLAGS) ${SDL2FLAGS}

clean:
	$(RM) $(TARGET)
