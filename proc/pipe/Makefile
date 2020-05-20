
LIBPYTHON = /home/david/code/anaconda3/envs/data/lib/
INCPYTHON = -I/home/david/code/anaconda3/envs/data/include/python3.7m/ \
			-I/home/david/code/anaconda3/lib/python3.7/site-packages/numpy/core/include



all:
	# cython3 --embed pipe2.pyx -o pipe.c 
	gcc pipe.c -o pipe $(INCPYTHON) -L $(LIBPYTHON)  -Wl,-rpath=$(LIBPYTHON) -lpython3.7m -lpthread -lm -lutil -ldl

annotate:
	cython3 -a pipe2.pyx

# TO RUN THE FILE:
# PYTHONHOME=/home/david/code/anaconda3 ./hello
#PYTHONHOME=/home/david/code/anaconda3 ./hello
