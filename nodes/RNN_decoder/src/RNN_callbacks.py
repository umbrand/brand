#! /usr/bin/env python

import pytorch_lightning as pl
import datetime as dt

from pytorch_lightning.callbacks import ModelSummary
from pprint import pprint

class RNNCallbacks(pl.Callback):

    def on_init_start(self, trainer):
        # Notify when Trainer initialization
        # starts.
        print('Initializing Trainer...')

    def on_init_end(self, trainer):
        # Notify when Trainer is initialized
        print('Trainer Initialized!\n')
        print('Preprocessing Data...')

    def on_fit_start(self, trainer, pl_module):
        # Print model architecture and number
        # of parameters
        ModelSummary(pl_module)
        print('\nHyperparameters:')
        pprint(pl_module.params)
    
    def on_train_start(self, trainer, pl_module):
        # Record Training start time
        self.start_time = dt.datetime.now()
        
        # Notify when Training starts
        print("\nStarting Training...")
            
    def on_train_end(self, trainer, pl_module):
        # Record Training end time
        self.end_time = dt.datetime.now()
        
        # Notify when training ends
        print('\nTraining Complete!\n')

        # Print Total Training time
        print(f'\nTraining Duration: {self.end_time - self.start_time}')

        # Print final R^2 values
        tr2 = trainer.logged_metrics['training R^2']
        vr2 = trainer.logged_metrics['val R^2']

        print(f'Final Training R^2: {tr2}')
        print(f'Final Validation R^2: {vr2}')

    def on_test_start(self, trainer, pl_module):
        # Notify when test starts
        print('\nTesting trained model...')