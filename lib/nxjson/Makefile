
all: nxjson

nxjson: nxjson.c test.c nxjson.h
	gcc -O0 -g -Wall ${CFLAGS} nxjson.c test.c -o nxjson

clean:
	rm nxjson

.PHONY: clean

CFLAGS 		= -g -Wall --shared -fPIC -Wno-parentheses

library:
	gcc $(CFLAGS) nxjson.c -o libnxjson.so -Wno-missing-braces

