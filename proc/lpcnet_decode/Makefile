PROJECT=lpcnet_decode

ROOT ?= ../..
include $(ROOT)/setenv.mk

CC = gcc
DEFAULTFLAGS = -Wall 
CFLAGS = $(DEFAULTFLAGS) -O3 -g -mavx2 -mfma

LINKS= -L$(HIREDIS_PATH) -L$(LPCNET_LIB_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH) -Wl,-rpath=$(LPCNET_LIB_PATH)
LDFLAGS = -lrt -pthread -lhiredis -llpcnet

CINCLUDE = -I$(ROOT)/lib/utilityFunctions/ \
		   -I$(ROOT)/lib/redisTools/ \
		   -I$(HIREDIS_PATH) \
		   -I$(ROOT)/lib/LPCNet/src/ \
		   -I$(ROOT)/lib/LPCNet/include \


CFILES = $(ROOT)/lib/utilityFunctions/utilityFunctions.c \
		 $(ROOT)/lib/redisTools/redisTools.c 

TARGET=$(BIN_PATH)/$(PROJECT)

all: lpcnet_decode

lpcnet_decode: lpcnet_decode.c
	$(CC) $(CFLAGS) $(CINCLUDE) lpcnet_decode.c $(CFILES) -o $(TARGET) $(LINKS) $(LDFLAGS) $(LDPATH)

clean:
	$(RM) $(TARGET)
