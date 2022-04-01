export ROOT ?= $(shell pwd)
include $(ROOT)/setenv.mk

# Get all directories in nodes/ that contain a Makefile
SUBDIR_BASE_PATH=nodes
SUBDIRS=$(notdir $(shell dirname $(wildcard $(SUBDIR_BASE_PATH)/*/Makefile)))

# make some clean targets for all subdirs
CLEANDIRS = $(SUBDIRS:%=clean-%)

# Get all directories in ../brand-modules/*/nodes/ that contain a Makefile
MODULES_SUBDIR_BASE_PATH=../brand-modules
#MODULES_SUBDIRS=$(notdir $(shell dirname $(wildcard $(MODULES_SUBDIR_BASE_PATH)/*/nodes/*/Makefile)))
MODULES_SUBDIRS=$(shell dirname $(wildcard $(MODULES_SUBDIR_BASE_PATH)/*/nodes/*/Makefile))

# make some clean targets for all subdirs
MODULES_CLEANDIRS = $(MODULES_SUBDIRS:%=clean-%)

all: $(SUBDIRS) $(MODULES_SUBDIRS) hiredis lpcnet redis

.PHONY: subdirs $(SUBDIRS)
.PHONY: subdirs $(CLEANDIRS)
.PHONY: modules_subdirs $(MODULES_SUBDIRS)
.PHONY: modules_subdirs $(MODULES_CLEANDIRS)

# make targets for all relevant paths under nodes/
$(SUBDIRS): hiredis lpcnet redis
	$(MAKE) -C $(SUBDIR_BASE_PATH)/$@

# make targets for all relevant paths under nodes/
$(MODULES_SUBDIRS): hiredis lpcnet redis
	$(MAKE) -C $(MODULES_SUBDIR_BASE_PATH)/$@

# Linking to hiredis seems to have a bug, where make
# attempt to link to an so filename with the full ver.
# ldconfig to automatically creates that file, and
# a tmp cache is specified to avoid requiring root perms.
hiredis: redis
	$(MAKE) -C $(HIREDIS_PATH)
	ldconfig -C /tmp/cache $(HIREDIS_PATH)
	$(RM) /tmp/cache

lpcnet: export CFLAGS = -O3 -g -mavx2 -mfma
lpcnet:
# if Makefile hasn't been generated run autogen and configure
ifeq ($(wildcard $(LPCNET_PATH)/Makefile), )
	cd $(LPCNET_PATH) && ./autogen.sh
	cd $(LPCNET_PATH) && ./configure
endif
	$(MAKE) -C $(LPCNET_PATH)

redis:
	$(MAKE) -C $(REDIS_PATH) redis-server redis-cli
	mv $(REDIS_PATH)/src/redis-server $(BIN_PATH)
	mv $(REDIS_PATH)/src/redis-cli $(BIN_PATH)

redis-test:
	$(MAKE) -C $(REDIS_PATH) test

clean-all: clean clean-hiredis clean-lpcnet

clean: $(CLEANDIRS) $(MODULES_CLEANDIRS)

$(CLEANDIRS):
	$(MAKE) -C $(SUBDIR_BASE_PATH)/$(@:clean-%=%) clean

$(MODULES_CLEANDIRS):
	$(MAKE) -C $(MODULES_SUBDIR_BASE_PATH)/$(@:clean-%=%) clean

clean-hiredis:
	$(MAKE) -C $(HIREDIS_PATH) clean
	$(RM) $(HIREDIS_PATH)/*.so*

clean-redis:
	$(MAKE) -C $(REDIS_PATH) clean
	$(RM) $(BIN_PATH)/redis-server $(BIN_PATH)/redis-cli

clean-lpcnet:
	$(MAKE) -C $(LPCNET_PATH) clean
