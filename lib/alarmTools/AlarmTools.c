
#include "AlarmTools.h"
#include <signal.h> // timer_create()
#include <time.h> // timer_create()
#include <sched.h> // set_scheduler()
#include <errno.h> //errno
#include <string.h> //strerror
#include <stdio.h>
#include <stdlib.h>

int InitializeAlarm(void (*handlerFunction)(int), int nSeconds, int nNanoseconds)
{

    struct sigaction sa = {0};
    sa.sa_handler 	= handlerFunction;
    sa.sa_flags 	= SA_RESTART;
//    sigemptyset(&sa.sa_mask);

	if(sigaction(SIGALRM, &sa, NULL) == -1)
	{
		printf("Could not initialize Signal: %s", strerror(errno));
		exit(1);
	}


    timer_t timerid = {0};

	struct itimerspec t 		= {0};
	t.it_value.tv_sec 			= nSeconds;
	t.it_value.tv_nsec 			= nNanoseconds;
	t.it_interval.tv_sec 		= t.it_value.tv_sec;
	t.it_interval.tv_nsec 		= t.it_value.tv_nsec;

	struct sigevent sev 		= {0};
    sev.sigev_notify 			= SIGEV_SIGNAL; // Send a signal
    sev.sigev_signo 			= SIGALRM; // The signal to send
    sev.sigev_value.sival_ptr 	= &timerid; // Dunno what this does

	if(timer_create(CLOCK_MONOTONIC, &sev, &timerid) < 0)
	{
		printf("Could not create timer: %s", strerror(errno));
		exit(1);
	}

	if(timer_settime(timerid, 0, &t, 0) < 0)
	{
		printf("Could not start timer: %s", strerror(errno));
		exit(1);		
	}

	return 0;

}

int CatchInterruptSignal(void (*handlerFunction)(int))
{
    struct sigaction sa = {0};
    sa.sa_handler 	= handlerFunction;

	if(sigaction(SIGINT, &sa, NULL) == -1)
	{
		printf("Could not initialize Signal: %s", strerror(errno));
		exit(1);
	}

    return 0;

}
