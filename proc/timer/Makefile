CC = gcc
ROOT = ../../
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS)

HIREDIS_PATH=$(ROOT)/lib/hiredis/

LINKS= -L$(HIREDIS_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH)
LDFLAGS = -lrt -pthread -lsqlite3 -lhiredis

CINCLUDE = -I$(ROOT)/lib/utilityFunctions/ \
		   -I$(ROOT)/lib/redisTools/ \
		   -I$(HIREDIS_PATH)


CFILES = $(ROOT)/lib/utilityFunctions/utilityFunctions.c \
		 $(ROOT)/lib/redisTools/redisTools.c

all: timer 

timer: timer.c 
	$(CC) $(CFLAGS) $(CINCLUDE) $(LINKS) timer.c $(CFILES) $(LDPATH) -o timer $(LDFLAGS)
