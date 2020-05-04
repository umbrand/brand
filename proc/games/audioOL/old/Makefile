
CFILES=/home/david/Documents/Projects/EmorySpeech/code/lib/alarmTools/AlarmTools.c \
	   /home/david/code/espa/Libraries/Tictoc/Source/Tictoc.c

INCLUDES= -I/home/david/Documents/Projects/EmorySpeech/code/lib/alarmTools \
	      -I/home/david/code/espa/Libraries/Tictoc/Source/


all:
	gcc soundPipe.c $(CFILES) $(INCLUDES) -o soundPipe -lrt -lpthread


sound:
	gcc soundMaker.c $(CFILES) $(INCLUDES) -o soundMaker -lrt -lpthread
