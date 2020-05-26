all: nxjson

nxjson: nxjson.c test.c nxjson.h
	gcc -O0 -g -Wall ${CFLAGS} nxjson.c test.c -o $(BIN_PATH)/nxjson

clean:
	$(RM) $(BIN_PATH)/*nxjson*

.PHONY: clean

CFLAGS 		= -g -Wall --shared -fPIC -Wno-parentheses

library:
	gcc $(CFLAGS) nxjson.c -o $(BIN_PATH)/libnxjson.so -Wno-missing-braces
