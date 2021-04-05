PROJECT=cursorTargetDisplay

ROOT ?= ../..
include $(ROOT)/setenv.mk

CC = gcc
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS)
SDL2FLAGS=$(shell pkg-config sdl2 --cflags --libs) -lSDL2_image

LINKS= -L$(HIREDIS_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH)
LDFLAGS = -lhiredis

CINCLUDE = -I$(ROOT)/lib/redisTools/ \
		   -I$(HIREDIS_PATH)


CFILES = $(ROOT)/lib/redisTools/redisTools.c

TARGET=$(BIN_PATH)/$(PROJECT)

all: cursorTargetDisplay

cursorTargetDisplay: cursorTargetDisplay.c
	$(CC) $(CFLAGS) $(CINCLUDE) $(LINKS) cursorTargetDisplay.c -pthread $(CFILES) $(LDPATH) -o $(TARGET) $(LDFLAGS) ${SDL2FLAGS}

clean:
	$(RM) $(TARGET)
