PROJECT=ecog

ROOT ?= ../..
include $(ROOT)/setenv.mk

CFILES = $(ROOT)/lib/alarmTools/AlarmTools.c \
         $(ROOT)/lib/nxjson/nxjson.c

# -lrt is needed for AlarmTools
#  -lpthread is needed for semaphores

INCLUDES= -I$(ROOT)/lib/alarmTools/ \
		  -I$(ROOT)/lib/nxjson/ \
		  -I$(HIREDIS_PATH)

LINKS= -L$(HIREDIS_PATH)
TARGET=$(BIN_PATH)/$(PROJECT)

all:
	gcc generator.c $(CFILES) $(INCLUDES) $(LINKS) -o $(TARGET) -Wl,-rpath=$(HIREDIS_PATH) -lpthread -lrt -lhiredis

pi:
	gcc generator.c AlarmTools.c -o generator -lpthread -lrt

clean:
	$(RM) $(TARGET)
