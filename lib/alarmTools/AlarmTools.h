/**

*/

int CatchInterruptSignal(void (*handlerFunction)(int));

int InitializeAlarm(void (*handlerFunction)(int), int nSeconds, int nNanoseconds);