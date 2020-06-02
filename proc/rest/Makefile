PROJECT=rest

ifneq ($(CONDA_DEFAULT_ENV),rt)
$(error real-time conda env (rt) not active)
endif

export ROOT ?= ../..
include $(ROOT)/setenv.mk

SUBDIRS= \
	elm \

CLEANDIRS = $(SUBDIRS:%=clean-%)

PYTHON_VERSION=3.8 # This works for rt env
PYTHON_LIB=python$(PYTHON_VERSION)

LIBPYTHON=$(CONDA_PREFIX)/lib/
INCPYTHON=$(CONDA_PREFIX)/include/$(PYTHON_LIB)

TARGET=$(BIN_PATH)/$(PROJECT)
CYTHON_TARGET=$(GENERATED_PATH)/$(PROJECT).c

all: $(SUBDIRS)
	cython --embed $(PROJECT).pyx -o $(CYTHON_TARGET)
	gcc $(CYTHON_TARGET) -o $(TARGET) -I $(INCPYTHON) -L $(LIBPYTHON)  -Wl,-rpath=$(LIBPYTHON) -l$(PYTHON_LIB) -lpthread -lm -lutil -ldl

.PHONY: subdirs $(SUBDIRS)
.PHONY: subdirs $(CLEANDIRS)

$(SUBDIRS):
	$(MAKE) -C $@

clean: $(CLEANDIRS)
	$(RM) $(TARGET) $(CYTHON_TARGET)

$(CLEANDIRS):
	$(MAKE) -C $(@:clean-%=%) clean
