export ROOT ?= $(shell pwd)
include $(ROOT)/setenv.mk

# Get all directories in nodes/ that contain a Makefile
SUBDIR_BASE_PATH=nodes
SUBDIRS=$(notdir $(shell dirname $(wildcard $(SUBDIR_BASE_PATH)/*/Makefile)))

# make some clean targets for all subdirs
CLEANDIRS = $(SUBDIRS:%=clean-%)

# Get all directories in ../brand-modules/*/nodes/ that contain a Makefile
MODULES_SUBDIR_BASE_PATH=../brand-modules
MODULES_SUBDIRS=$(shell dirname $(wildcard $(MODULES_SUBDIR_BASE_PATH)/*/nodes/*/Makefile))

# make some clean targets for all subdirs
MODULES_CLEANDIRS = $(MODULES_SUBDIRS:%=clean-%)

all: $(SUBDIRS) $(MODULES_SUBDIRS) hiredis redis

.PHONY: subdirs $(SUBDIRS)
.PHONY: subdirs $(CLEANDIRS)
.PHONY: modules_subdirs $(MODULES_SUBDIRS)
.PHONY: modules_subdirs $(MODULES_CLEANDIRS)

# make targets for all relevant paths under nodes/
$(SUBDIRS): hiredis redis
	$(MAKE) -C $(SUBDIR_BASE_PATH)/$@

# make targets for all relevant paths under ../brand-modules/*/nodes/
$(MODULES_SUBDIRS): hiredis redis
	@git -C $@ rev-parse; IS_GIT=$$?; \
	if [ $$IS_GIT = 0 ]; then \
		echo -n $$(git -C $@ rev-parse HEAD) > $@/git_hash.o; \
	fi
	$(MAKE) -C $(MODULES_SUBDIR_BASE_PATH)/$@


# Linking to hiredis seems to have a bug, where make
# attempt to link to an so filename with the full ver.
# ldconfig to automatically creates that file, and
# a tmp cache is specified to avoid requiring root perms.
hiredis: redis
	$(MAKE) -C $(HIREDIS_PATH)
	ldconfig -C /tmp/cache $(HIREDIS_PATH)
	$(RM) /tmp/cache

redis:
	$(MAKE) -C $(REDIS_PATH) redis-server redis-cli
	mv $(REDIS_PATH)/src/redis-server $(BIN_PATH)
	mv $(REDIS_PATH)/src/redis-cli $(BIN_PATH)

redis-test:
	$(MAKE) -C $(REDIS_PATH) test

clean-all: clean clean-hiredis

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

