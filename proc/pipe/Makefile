
LIBPYTHON = /home/david/code/anaconda3/envs/data/lib/
INCPYTHON = /home/david/code/anaconda3/envs/data/include/python3.7m/

all:
	cython3 --embed pipe.pyx -o pipe.c
	gcc pipe.c -o pipe -I $(INCPYTHON) -L $(LIBPYTHON)  -Wl,-rpath=$(LIBPYTHON) -lpython3.7m -lpthread -lm -lutil -ldl

# TO RUN THE FILE:
# PYTHONHOME=/home/david/code/anaconda3 ./hello
#PYTHONHOME=/home/david/code/anaconda3 ./hello
