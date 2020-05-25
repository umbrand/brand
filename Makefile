export ROOT=$(shell pwd)
THIRD_PARTY=$(ROOT)/third-party
REDIS_PATH=$(THIRD_PARTY)/redis
REDIS_SERVER_FULL_PATH=$(REDIS_PATH)/src/redis-server

export HIREDIS_PATH=$(THIRD_PARTY)/hiredis
export BIN_PATH=$(ROOT)/bin
export GENERATED_PATH=$(BIN_PATH)/generated
$(shell mkdir -p $(GENERATED_PATH))

PROC_PATH=proc/
SUBDIRS= \
	$(PROC_PATH)generator \
	$(PROC_PATH)pipe \
	$(PROC_PATH)streamUDP \
	$(PROC_PATH)timer \

CLEANDIRS = $(SUBDIRS:%=clean-%)

all: $(SUBDIRS) hiredis redis

.PHONY: subdirs $(SUBDIRS)
.PHONY: subdirs $(CLEANDIRS)

$(SUBDIRS): hiredis redis
	$(MAKE) -C $@

hiredis: redis
	$(MAKE) -C $(HIREDIS_PATH)
	ldconfig -C /tmp/cache $(HIREDIS_PATH)
	$(RM) /tmp/cache

redis:
	$(MAKE) -C $(REDIS_PATH)
	cp $(REDIS_SERVER_FULL_PATH) $(BIN_PATH)

test_redis:
	$(MAKE) -C $(REDIS_PATH) test

clean_all: clean clean_redis clean_hiredis

clean: $(CLEANDIRS)

$(CLEANDIRS):
	$(MAKE) -C $(@:clean-%=%) clean

clean_redis:
	$(MAKE) -C $(REDIS_PATH) clean

clean_hiredis:
	$(MAKE) -C $(HIREDIS_PATH) clean
	$(RM) $(HIREDIS_PATH)/*.so*
