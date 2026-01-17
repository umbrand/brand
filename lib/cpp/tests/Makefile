PROJECTS=msgpack_roundtrip_writer msgpack_roundtrip_cpp_reader

ROOT ?= ../../../
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

TARGETS=$(addsuffix .bin, $(PROJECTS))

COBJS = nxjson.o
CXXOBJS_COMMON = node.o
CXXOBJS_WRITER = msgpack_roundtrip_writer.o
CXXOBJS_READER = msgpack_roundtrip_cpp_reader.o

all: $(TARGETS)

nxjson.o: $(ROOT)/lib/nxjson/nxjson.c
	$(CC) $(CFLAGS) $(CXXINCLUDE) -c $< -o $@

node.o: $(ROOT)/lib/cpp/brand/node.cpp
	$(CXX) $(CXXFLAGS) $(CXXINCLUDE) -c $< -o $@

msgpack_roundtrip_writer.o: msgpack_roundtrip_writer.cpp
	$(CXX) $(CXXFLAGS) $(CXXINCLUDE) -c $< -o $@

msgpack_roundtrip_cpp_reader.o: msgpack_roundtrip_cpp_reader.cpp
	$(CXX) $(CXXFLAGS) $(CXXINCLUDE) -c $< -o $@

msgpack_roundtrip_writer.bin: $(COBJS) $(CXXOBJS_COMMON) $(CXXOBJS_WRITER)
	$(CXX) $(LINKS) $(COBJS) $(CXXOBJS_COMMON) $(CXXOBJS_WRITER) $(LDPATH) -o $@ $(LDFLAGS)

msgpack_roundtrip_cpp_reader.bin: $(COBJS) $(CXXOBJS_COMMON) $(CXXOBJS_READER)
	$(CXX) $(LINKS) $(COBJS) $(CXXOBJS_COMMON) $(CXXOBJS_READER) $(LDPATH) -o $@ $(LDFLAGS)

clean:
	$(RM) $(TARGETS) $(COBJS) $(CXXOBJS_COMMON) $(CXXOBJS_WRITER) $(CXXOBJS_READER)
