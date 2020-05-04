


HIREDIS_PATH=../../lib/hiredis/

all:
	gcc udpAdapter.c -o udpAdapter -I$(HIREDIS_PATH) -L.$(HIREDIS_PATH) -Wl,-rpath=$(HIREDIS_PATH) -lhiredis
	# gcc udpAdapter.c -o udpAdapter -I$(HIREDIS_PATH) -L.$(HIREDIS_PATH) -Wl,-rpath=/usr/local/lib/ -lhiredis




