export ROOT ?= $(shell pwd)
include $(ROOT)/setenv.mk

# Get all directories in proc/ that contain a Makefile
SUBDIR_BASE_PATH=proc
SUBDIRS=$(notdir $(shell dirname $(wildcard $(SUBDIR_BASE_PATH)/*/Makefile)))

# make some clean targets for all subdirs
CLEANDIRS = $(SUBDIRS:%=clean-%)

all: $(SUBDIRS) hiredis lpcnet

.PHONY: subdirs $(SUBDIRS)
.PHONY: subdirs $(CLEANDIRS)

# make targets for all relevant paths under proc/
$(SUBDIRS): hiredis lpcnet redis
	$(MAKE) -C $(SUBDIR_BASE_PATH)/$@

# Linking to hiredis seems to have a bug, where make
# attempt to link to an so filename with the full ver.
# ldconfig to automatically creates that file, and
# a tmp cache is specified to avoid requiring root perms.
hiredis:
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
	$(MAKE) -C $(REDIS_PATH)



clean-all: clean clean-hiredis clean-lpcnet

clean: $(CLEANDIRS)

$(CLEANDIRS):
	$(MAKE) -C $(@:clean-%=%) clean

clean-hiredis:
	$(MAKE) -C $(HIREDIS_PATH) clean
	$(RM) $(HIREDIS_PATH)/*.so*

clean-lpcnet:
	$(MAKE) -C $(LPCNET_PATH) clean
