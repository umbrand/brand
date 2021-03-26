PROJECT=mouse_ac

ROOT ?= ../..
include $(ROOT)/setenv.mk

CC = gcc
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS)

LINKS= -L$(HIREDIS_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH)
LDFLAGS = -lhiredis

CINCLUDE = -I$(ROOT)/lib/redisTools/ \
		   -I$(HIREDIS_PATH)


CFILES = $(ROOT)/lib/redisTools/redisTools.c

TARGET=$(BIN_PATH)/$(PROJECT)

all: mouse_ac

redis_test: redis_test.c
	$(CC) $(CFLAGS) $(CINCLUDE) $(LINKS) redis_test.c $(CFILES) $(LDPATH) -o $(TARGET) $(LDFLAGS)

mouse_ac: mouse_ac.c
	$(CC) $(CFLAGS) $(CINCLUDE) $(LINKS) mouse_ac.c -pthread $(CFILES) $(LDPATH) -o $(TARGET) $(LDFLAGS)

clean:
	$(RM) $(TARGET)
