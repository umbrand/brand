CC = gcc
ROOT = ../../
DEFAULTFLAGS = -Wall 
CFLAGS = $(DEFAULTFLAGS) -O3 -g -mavx2 -mfma

HIREDIS_PATH=$(ROOT)/lib/hiredis/
LPCNET_PATH=$(ROOT)/lib/LPCNet/.libs/

LINKS= -L$(HIREDIS_PATH) -L$(LPCNET_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH) -Wl,-rpath=$(LPCNET_PATH)
LDFLAGS = -lrt -pthread -lhiredis -llpcnet

CINCLUDE = -I$(ROOT)/lib/utilityFunctions/ \
		   -I$(ROOT)/lib/redisTools/ \
		   -I$(HIREDIS_PATH) \
		   -I$(ROOT)/lib/LPCNet/src/ \
		   -I$(ROOT)/lib/LPCNet/include \


CFILES = $(ROOT)/lib/utilityFunctions/utilityFunctions.c \
		 $(ROOT)/lib/redisTools/redisTools.c 

all: lpcnet_encode

lpcnet_encode: lpcnet_encode.c
	$(CC) $(CFLAGS) $(CINCLUDE) lpcnet_encode.c $(CFILES) -o lpcnet_encode $(LINKS) $(LDFLAGS) $(LDPATH)

