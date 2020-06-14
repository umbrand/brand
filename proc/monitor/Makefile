PROJECT=monitor

ROOT ?= ../..
include $(ROOT)/setenv.mk

CC = gcc
DEFAULTFLAGS = -Wall 
CFLAGS = $(DEFAULTFLAGS) -O3 -g -mavx2 -mfma

LINKS= -L$(HIREDIS_PATH) -L$(LPCNET_LIB_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH) -Wl,-rpath=$(LPCNET_LIB_PATH)
LDFLAGS = -lrt -pthread -lhiredis

CINCLUDE = -I$(ROOT)/lib/redisTools/ \
		   -I$(HIREDIS_PATH) \
		   -I$(ROOT)/lib/alarmTools/


CFILES = $(ROOT)/lib/redisTools/redisTools.c \
		 $(ROOT)/lib/alarmTools/AlarmTools.c 


TARGET=$(BIN_PATH)/$(PROJECT)

all: monitor

monitor: monitor.c
	$(CC) $(CFLAGS) $(CINCLUDE) monitor.c $(CFILES) -o $(TARGET) $(LINKS) $(LDFLAGS) $(LDPATH)

clean:
	$(RM) $(TARGET)
