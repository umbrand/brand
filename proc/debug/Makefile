CC = gcc
ROOT = ../../
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS)
LDFLAGS = -lrt -pthread -lsqlite3
CINCLUDE = -I$(ROOT)/lib/utilityFunctions/ 

CFILES = $(ROOT)/lib/utilityFunctions/utilityFunctions.c 

all: debug 

debug: debug.c
	$(CC) $(CFLAGS) $(CINCLUDE) debug.c $(CFILES) -o debug $(LDFLAGS)

