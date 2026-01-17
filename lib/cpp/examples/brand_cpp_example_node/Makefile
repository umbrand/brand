PROJECT=cpp_example_node

ROOT ?= ../../../../
include $(ROOT)/setenv.mk

CXX = g++
CC = gcc
DEFAULTFLAGS = -Wall
CXXDEFAULTFLAGS = -Wall --std=c++17
CFLAGS = -O2 $(DEFAULTFLAGS)
CXXFLAGS = -O2 $(CXXDEFAULTFLAGS)

MSGPACK_CFLAGS ?= $(shell pkg-config --cflags msgpack 2>/dev/null)
MSGPACK_LIBS ?= $(shell pkg-config --libs msgpack 2>/dev/null)

LINKS = -L$(HIREDIS_PATH)
LDPATH = -Wl,-rpath=$(HIREDIS_PATH)
LDFLAGS = -lhiredis -lmsgpackc -pthread $(MSGPACK_LIBS)

CXXINCLUDE = $(MSGPACK_CFLAGS) -I$(ROOT)/lib/cpp \
			 -I$(HIREDIS_PATH) \
			 -I$(ROOT)/lib/nxjson \
			 -I$(ROOT)/lib/utilityFunctions

TARGET=$(PROJECT).bin

COBJS = nxjson.o
CXXOBJS = cpp_example_node.o node.o

all: $(PROJECT)

nxjson.o: $(ROOT)/lib/nxjson/nxjson.c
	$(CC) $(CFLAGS) $(CXXINCLUDE) -c $< -o $@

node.o: $(ROOT)/lib/cpp/brand/node.cpp
	$(CXX) $(CXXFLAGS) $(CXXINCLUDE) -c $< -o $@

cpp_example_node.o: cpp_example_node.cpp
	$(CXX) $(CXXFLAGS) $(CXXINCLUDE) -c $< -o $@

$(PROJECT): $(COBJS) $(CXXOBJS)
	$(CXX) $(LINKS) $(COBJS) $(CXXOBJS) $(LDPATH) -o $(TARGET) $(LDFLAGS)

clean:
	$(RM) $(TARGET) $(COBJS) $(CXXOBJS)
