PROJECT=replay

ROOT ?= ../..
include $(ROOT)/setenv.mk

# Deliberately ignore unused result flag, since we don't want to check write() in main loop
CC = gcc
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS) -Wno-unused-result
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS) 

LINKS= -L$(HIREDIS_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH)
LDFLAGS = -lrt -pthread -lsqlite3 -lhiredis

CINCLUDE = -I$(ROOT)/lib/utilityFunctions/ \
		   -I$(ROOT)/lib/redisTools/ \
		   -I$(ROOT)/lib/alarmTools/ \
		   -I$(HIREDIS_PATH)


CFILES = $(ROOT)/lib/utilityFunctions/utilityFunctions.c \
		 $(ROOT)/lib/redisTools/redisTools.c \
		 $(ROOT)/lib/alarmTools/AlarmTools.c 

TARGET=$(BIN_PATH)/$(PROJECT)

all: replay

replay: replay.c
	$(CC) $(CFLAGS) $(CINCLUDE) $(LINKS) replay.c $(CFILES) $(LDPATH) -o $(TARGET) $(LDFLAGS)

clean:
	$(RM) $(TARGET)
