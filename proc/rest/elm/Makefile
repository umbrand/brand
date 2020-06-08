ROOT ?= ../../..
include $(ROOT)/setenv.mk
ELM_PATH=$(BIN_PATH)
ELM=$(ELM_PATH)/elm
OUTPUT=../static/js/main.js

all:
	$(ELM) $(MAKE) Main.elm --output $(OUTPUT)

clean:
	$(RM) $(OUTPUT)

