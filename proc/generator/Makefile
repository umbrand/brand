CC = gcc
ROOT = ../../
DEFAULTFLAGS = -Wall 
CFLAGS = -O2 $(DEFAULTFLAGS)
CFLAGSUNOPT = -O0 $(DEFAULTFLAGS)
CFLAGS+ = -g -O2 $(DEFAULTFLAGS)

HIREDIS_PATH=$(ROOT)/lib/hiredis/

LINKS= -L$(HIREDIS_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH)
LDFLAGS = -lrt -pthread -lsqlite3 -lhiredis -levent

CINCLUDE = -I$(ROOT)/lib/utilityFunctions/ \
		   -I$(ROOT)/lib/redisTools/ \
		   -I$(ROOT)/lib/alarmTools/ \
		   -I$(HIREDIS_PATH)


CFILES = $(ROOT)/lib/utilityFunctions/utilityFunctions.c \
		 $(ROOT)/lib/redisTools/redisTools.c \
		 $(ROOT)/lib/alarmTools/AlarmTools.c 

all: generator

generator: generator.c
	$(CC) $(CFLAGS) $(CINCLUDE) generator.c $(CFILES) -o generator $(LDFLAGS)

# ROOT=../..

# HIREDIS_PATH=$(ROOT)/lib/hiredis/

# CFILES = $(ROOT)/lib/alarmTools/AlarmTools.c \
#          $(ROOT)/lib/nxjson/nxjson.c

# # -lrt is needed for AlarmTools
# #  -lpthread is needed for semaphores

# INCLUDES= -I$(ROOT)/lib/alarmTools/ \
# 		  -I$(ROOT)/lib/nxjson/ \
# 		  -I$(HIREDIS_PATH)


# LINKS= -L$(HIREDIS_PATH)

# all:
# 	gcc generator.c $(CFILES) $(INCLUDES) $(LINKS) -o generator -Wl,-rpath=$(HIREDIS_PATH) -lpthread -lrt -lhiredis

# pi:
# 	gcc generator.c AlarmTools.c -o generator -lpthread -lrt
