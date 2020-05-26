PROJECT=pipe

ifneq ($(CONDA_DEFAULT_ENV),rt)
$(error real-time conda env (rt) not active)
endif

PYTHON_VERSION=3.8 # This works for rt env
PYTHON_LIB=python$(PYTHON_VERSION)

LIBPYTHON=$(CONDA_PREFIX)/lib/
INCPYTHON=$(CONDA_PREFIX)/include/$(PYTHON_LIB)

TARGET=$(BIN_PATH)/$(PROJECT)
CYTHON_TARGET=$(GENERATED_PATH)/pipe.c

all:
	cython --embed pipe.pyx -o $(CYTHON_TARGET)
	gcc $(CYTHON_TARGET) -o $(TARGET) -I $(INCPYTHON) -L $(LIBPYTHON)  -Wl,-rpath=$(LIBPYTHON) -l$(PYTHON_LIB) -lpthread -lm -lutil -ldl

clean:
	$(RM) $(TARGET) $(CYTHON_TARGET)

# TO RUN THE FILE:
# PYTHONHOME=/home/david/code/anaconda3 ./hello
#PYTHONHOME=/home/david/code/anaconda3 ./hello
