
ROOT=../..

HIREDIS_PATH=$(ROOT)/lib/hiredis/

CFILES = $(ROOT)/lib/alarmTools/AlarmTools.c \
         $(ROOT)/lib/nxjson/nxjson.c

# -lrt is needed for AlarmTools
#  -lpthread is needed for semaphores

INCLUDES= -I$(ROOT)/lib/alarmTools/ \
		  -I$(ROOT)/lib/nxjson/ \
		  -I$(HIREDIS_PATH)


LINKS= -L$(HIREDIS_PATH)

all:
	gcc generator.c $(CFILES) $(INCLUDES) $(LINKS) -o generator -Wl,-rpath=$(HIREDIS_PATH) -lpthread -lrt -lhiredis

pi:
	gcc generator.c AlarmTools.c -o generator -lpthread -lrt
