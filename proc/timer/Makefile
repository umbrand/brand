CC = gcc
ROOT = ../../
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS)
LDFLAGS = -lrt -pthread -lsqlite3
CINCLUDE = -I$(ROOT)/lib/utilityFunctions/ 

CFILES = $(ROOT)/lib/utilityFunctions/utilityFunctions.c 

all: timer 

timer: timer.c 
	$(CC) $(CFLAGS) $(CINCLUDE) timer.c $(CFILES) -o timer $(LDFLAGS)

