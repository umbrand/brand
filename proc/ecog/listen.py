# Listen.py
# Allows someone to listen to neural data
# Can be used either with a pre-recorded dataset or by using a stream
# Outputs data to ffplay which sits and listens to a piped output
#
# David Brandman April 2020


#python -c "import sys; import numpy as np; a=16000; n=5; fs=1000; f=440; sys.stdout.buffer.write(bytes((a*np.sin(np.linspace(0,f*2*np.pi*n,fs*n))).astype('int16')))" | ffplay -f s16le -ac 1 -ar 1000 - > listen.py

import subprocess
import numpy as np
import sys
import os
import redis
import scipy.io
import scipy.signal

sys.path.insert(1, '../../lib/')
from redisTools import *

fs = 1000

def loadMatEcogData(matFileName):
    matFile = scipy.io.loadmat( matFileName, squeeze_me = True, struct_as_record = False)
    return matFile['data'] 


if __name__ == "__main__":

    r = initializeRedisFromYAML('audioOL')

    data = loadMatEcogData('/home/david/code/kaiMillerSpeech/rawdata/speech_basic/data/bp_verbs.mat')



    ffplayString = ["ffplay" \
            , "-autoexit"
            # , "-nodisp"
            , "-hide_banner -loglevel panic" \
            , "-ar" , str(fs)
            , "-ac 1"
            , "-f s16le"
            , "-i pipe:0"

            ]

    ffplayString = " ".join(ffplayString)

    print("[Listen] Executing: ", ffplayString)
    h_ffplay = subprocess.Popen(ffplayString, stdin=subprocess.PIPE, shell=True, preexec_fn=os.setsid)

    n = 5
    f = 440
    a = 100
    chan = 30
    nyq = 0.5 * fs
    butLow = 100
    butHigh = 400
    Q = 60
    rawData = a*data[:,chan]
    filteredData = rawData

    b,a = scipy.signal.butter(8,[butLow/nyq, butHigh/nyq], btype='bandpass', analog=False)
    filteredData = scipy.signal.filtfilt(b,a,filteredData)

    b, a = scipy.signal.iirnotch(120/nyq,Q=Q)
    filteredData = scipy.signal.lfilter(b,a,filteredData)

    b, a = scipy.signal.iirnotch(180/nyq,Q=Q)
    filteredData = scipy.signal.lfilter(b,a,filteredData)



    h_ffplay.communicate(bytes(filteredData.astype('int16')))

    # (a*np.sin(np.linspace(0,f*2*np.pi*n,fs*n))).astype('int16')))
    # sys.stdout.buffer.write(bytes((a*np.sin(np.linspace(0,f*2*np.pi*n,fs*n))).astype('int16')))
    # h_ffplay.communicate(bytes((a*np.sin(np.linspace(0,f*2*np.pi*n,fs*n))).astype('int16')))





