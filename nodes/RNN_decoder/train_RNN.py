#! /usr/bin/env python

import torch
import pickle
import yaml
import datetime as dt
import os
import numpy as np
import matplotlib.pyplot as plt

from src.RNN_model import RNN
from src.RNN_callbacks import RNNCallbacks
from src.RNN_dataModule import RNNDataModule
from pytorch_lightning.loggers import TensorBoardLogger
from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import EarlyStopping
from pytorch_lightning.callbacks import LearningRateMonitor
from pathlib import Path
from snel_toolkit.interfaces import chop_data
from sklearn.metrics import r2_score

class RNNTrainer():
    def __init__(self):
        """ Initializes RNN model, Training
        Parameters, loggers, and datamodules.
        """

        # Define Parameters from YAML file
        with open('src/train_RNN.yaml', 'r') as file:
            self.params = yaml.safe_load(file)

        # create model object
        self.model = RNN()

        # Create logger object
        day = dt.datetime.now().strftime('%m-%d-%y')
        self.logger = TensorBoardLogger(
            save_dir=self.params['training']['log_pth'], 
            name=self.params['training']['log_name']+day
        )

        # Create RNN datamodule
        self.RNN_module = RNNDataModule()

    def train_RNN(self):
        """ Creates Trainer object and trains 
        the model.
        """

        # Define Early Stopping Callback
        early_stop = EarlyStopping(
            monitor='val_loss',
            patience=self.params['callbacks']['early_stop_patience'],
            mode='min'
        )

        # Define Learning Rate Callback
        lr_monitor = LearningRateMonitor(
            logging_interval='epoch'
        )

        # Create Trainer object
        trainer = Trainer(
            callbacks=[
                RNNCallbacks(),
                early_stop,
                lr_monitor    
            ],
            logger=self.logger,
            log_every_n_steps=self.params['training']['n_steps'],
            max_epochs = self.params['training']['max_epochs']
        )

        # Train model
        trainer.fit(self.model, datamodule=self.RNN_module)

    
    def plot_reaches(self):
        """ Plots the True vs Predicted trajectories
        and evaluates the model's performance for
        the test set.
        """
        # Put model in evaluation mode
        self.model.eval()

        # Preprocess data for model input
        test_spikes = self.RNN_module.spike_scalar.transform(
            self.RNN_module.test_data.spikes.values
        )

        spk_segments = chop_data(
                test_spikes, 
                self.params['datamodule']['overlap'], 
                self.params['datamodule']['seq_len']
            )
        spk_segments = torch.Tensor(spk_segments)

        # Produce velocity predictions
        with torch.no_grad():
            preds = self.model(spk_segments)
            preds = preds.numpy()

        # Scale velocities back to original size
        reg_preds = self.RNN_module.vel_scalar.inverse_transform(preds)

        # Create plot
        fig = plt.figure(figsize=(25,25))
        plt.subplots_adjust(hspace=0.6, wspace=0.3)

        # Remove first few entries due to chops
        trial_data = self.RNN_module.test_data[self.params['datamodule']['overlap']:].reset_index()
        trials = self.RNN_module.test_data['trial_id'].unique()

        # Evaluate model's performance
        reg_vels = trial_data[['cursor_velx', 'cursor_vely']].values
        r2_test = r2_score(reg_vels, reg_preds)
        print(f'Test R^2 score: {r2_test}')
        
        # Calculate number of rows/cols needed for plot
        num_trials = len(trials)
        factor = np.sqrt(num_trials)

        nrows = int(np.ceil(factor))
        ncols = int(np.ceil(factor))

        # Plot pred vs true trajectories by trial
        for i, trial in enumerate(trials):
            ax = plt.subplot(nrows, ncols, i+1)
            
            trial_idxs = trial_data.loc[trial_data['trial_id'] == trial].index
            x_pos = trial_data.loc[trial_idxs]['cursor_pos']['x_0']
            y_pos = trial_data.loc[trial_idxs]['cursor_pos']['x_1']
            x_preds = np.cumsum(reg_preds[trial_idxs, 0])
            y_preds = np.cumsum(reg_preds[trial_idxs, 1])
            ax.plot(x_pos, y_pos, color='blue')
            ax.plot(x_preds + x_pos.iloc[0], y_preds + y_pos.iloc[0], color='red')
            ax.set_title(f'Trial {trial}')

        fig.suptitle(
            f'True vs Predicted Trajectories (Test set), r2: {r2_test}',
            fontsize=30
        )
        
        # Save the figure
        fig.savefig(
            'RNNTruevsPred_test.png', 
            facecolor='white', 
            transparent=False
        )
    
    def save_model_info(self):
        """ Saves model weights as .pt file and data
        scalars into a pickle file. Model weights are
        saved with the corresponding date and time.
        """

        # Store path to save weights to
        save_pth = Path(self.params['training']['save_pth'])
        
        # UNCOMMENT AFTER DIR SETUP
        # if not os.path.exists(save_pth):
        #     raise FileNotFoundError("Specified directory not found")
        
        #check if dir exists, if not create one (DELETE AFTER DIR SETUP IS CREATED)
        if not os.path.isdir(save_pth):
            os.makedirs(save_pth)

        # Save model weights
        time = dt.datetime.now().strftime('%m-%d-%y_%X')
        weight_pth = os.path.join(save_pth, Path('RNN_weights_'+time+'.pt'))
        torch.save(self.model.state_dict(), weight_pth)

        # Save scalar objects for realtime decoding
        spk_scalar = self.RNN_module.spike_scalar
        vel_scalar = self.RNN_module.vel_scalar

        scalar_pth = os.path.join(save_pth, Path('RNN_scalars_'+time+'.pkl'))
        with open(scalar_pth, 'wb') as f:
            pickle.dump(spk_scalar, f)
            pickle.dump(vel_scalar, f)

        #save weight/scalar paths to YAML file
        weight_pth = Path(weight_pth).resolve()
        scalar_pth = Path(scalar_pth).resolve()
        self.params['real-time']['saved_weights'] = str(weight_pth)
        self.params['real-time']['saved_scalars'] = str(scalar_pth)

        with open('src/train_RNN.yaml', 'w') as file:
            yaml.safe_dump(self.params, file)
    

if __name__ == "__main__":
    rnn_trainer = RNNTrainer()
    rnn_trainer.train_RNN()
    rnn_trainer.save_model_info()
    rnn_trainer.plot_reaches()