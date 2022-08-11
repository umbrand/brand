#!/bin/bash

cd OLE
python ole_timing_test.py
cd ../RNN
python rnn_timing_test.py
cd ../NDT
python ndt_timing_test.py
cd ../PubSub
python pubsub_timing_test.py