PROJECT=generator

CC = gcc
ROOT = ../../
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
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

all: generator

generator: generator.c
	$(CC) $(CFLAGS) $(CINCLUDE) $(LINKS) generator.c $(CFILES) $(LDPATH) -o $(TARGET) $(LDFLAGS)

clean:
	$(RM) $(TARGET)
