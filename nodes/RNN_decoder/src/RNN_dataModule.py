#! /usr/bin/env python

import torch
import pytorch_lightning as pl
import yaml

from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from snel_toolkit.interfaces import chop_data
from snel_toolkit.datasets.brand import BRANDDataset

class RNNDataModule(pl.LightningDataModule):
    """ PyTorch Lightning DataModule class that
    Loads, Preprocesses, and Extracts features
    specifically for RNN training. Training,
    Validation, and Test Dataloaders are created 
    here.
    """

    def __init__(self):
        super().__init__()
        
        # Define Parameters from YAML file
        with open('src/train_RNN.yaml', 'r') as file:
            self.params = yaml.safe_load(file)

        # Initialize Scalar Objects
        self.spike_scalar = StandardScaler()
        self.vel_scalar = MinMaxScaler(feature_range=(-1,1))
    
    def prepare_data(self):
        """ Loads NWB file from specified directory,
        creates snel-toolkit DataFrame, and extracts
        necessary features for training.
        """
        
        # Define Path to NWB file
        NWB_file = self.params['training']['data_dir']

        # Create NWB Dataframe
        self.NWB_dataset = BRANDDataset(fpath=NWB_file)
        self.NWB_dataset.load(fpath=NWB_file)

        # Resample data according to specified bin size
        self.NWB_dataset.resample(
            self.params['training']['bin_size'],
            average_continuous=True    
        )

        # Create trial data
        self.NWB_trials = self.NWB_dataset.make_trial_data()
        self.NWB_trials.sort_index(axis=1, inplace=True)

        # Loop through trials and calculate cursor velocities
        self.trials = self.NWB_trials['trial_id'].unique()

        #--------------------------------------------------------------------#
        #           CODE BELOW TO USE WHEN SYSTEM DEV IS COMPLETE
        #--------------------------------------------------------------------#
        
        # for trial in self.trials:
        #     # Find indices corresponding to trial
        #     trial_idxs = self.NWB_trials.loc[self.NWB_trials['trial_id'] == trial].index
            
        #     # Extract cursor positions for the trial
        #     xpos = self.NWB_trials.loc[trial_idxs]['cursor_pos']['x_0'].values
        #     ypos = self.NWB_trials.loc[trial_idxs]['cursor_pos']['x_1'].values
            
        #     # Calculate cursor velocities from positions
        #     self.NWB_trials.loc[trial_idxs, 'cursor_velx'] = np.gradient(xpos)
        #     self.NWB_trials.loc[trial_idxs, 'cursor_vely'] = np.gradient(ypos)
        
        #--------------------------------------------------------------------#
        # CODE BELOW TO USE WHILE TESTING, DELETE AFTER SYSTEM DEV IS COMPLETE
        #--------------------------------------------------------------------#
        
        #Pick the 1st 500 trials
        num_trials = 500
        self.used_trials = self.trials[:num_trials]

        #Extract data from trials included in used_trials
        self.NWB_used = self.NWB_trials.loc[self.NWB_trials['trial_id'].isin(self.used_trials)]

        for trial in self.used_trials:
            # Find indices corresponding to trial
            trial_idxs = self.NWB_used.loc[self.NWB_used['trial_id'] == trial].index
            
            # Extract cursor positions for the trial
            xpos = self.NWB_used.loc[trial_idxs]['cursor_pos']['x_0'].values
            ypos = self.NWB_used.loc[trial_idxs]['cursor_pos']['x_1'].values
            
            # Calculate cursor velocities from positions
            self.NWB_used.loc[trial_idxs, 'cursor_velx'] = np.gradient(xpos)
            self.NWB_used.loc[trial_idxs, 'cursor_vely'] = np.gradient(ypos)
    
    def split_dataset(self):
        """ Splits the loaded data randomly
        into training, validation, and test
        sets based on specified percentages
        in the training YAML file.
        """

        #--------------------------------------------------------------------#
        #           CODE BELOW TO USE WHEN SYSTEM DEV IS COMPLETE
        #--------------------------------------------------------------------#

        # #Define split percentages of dataset
        # train_percent = self.params['training']['train_pct']
        # val_percent = self.params['training']['val_pct']
        
        # #Calculate how many trials for each set
        # num_train = int(len(self.trials) * train_percent)
        # num_val = int(len(self.trials) * val_percent)

        # #Randomly pick trials for each set
        # train_trials = np.random.choice(self.trials, num_train, replace=False)
        # trials_left = np.delete(self.trials, train_trials)
        # val_trials = np.random.choice(trials_left, num_val, replace=False)
        # trials_left = np.delete(self.trials, np.concatenate((train_trials, val_trials)))
        # test_trials = trials_left

        # #Extract data from trials included in each set
        # self.train_data = self.NWB_trials.loc[self.NWB_trials['trial_id'].isin(train_trials)]
        # self.val_data = self.NWB_trials.loc[self.NWB_trials['trial_id'].isin(val_trials)]
        # self.test_data = self.NWB_trials.loc[self.NWB_trials['trial_id'].isin(test_trials)]
        
        #--------------------------------------------------------------------#
        # CODE BELOW TO USE WHILE TESTING, DELETE AFTER SYSTEM DEV IS COMPLETE
        #--------------------------------------------------------------------#
        
        #Define split percentages of dataset
        train_percent = self.params['training']['train_pct']
        val_percent = self.params['training']['val_pct']
        
        #Calculate how many trials for each set
        num_train = int(len(self.used_trials) * train_percent)
        num_val = int(len(self.used_trials) * val_percent)

        #Randomly pick trials for each set
        train_trials = np.random.choice(self.used_trials, num_train, replace=False)
        trials_left = np.delete(self.used_trials, train_trials)
        val_trials = np.random.choice(trials_left, num_val, replace=False)
        trials_left = np.delete(self.used_trials, np.concatenate((train_trials, val_trials)))
        test_trials = trials_left

        #Extract data from trials included in each set
        self.train_data = self.NWB_used.loc[self.NWB_used['trial_id'].isin(train_trials)]
        self.val_data = self.NWB_used.loc[self.NWB_used['trial_id'].isin(val_trials)]
        self.test_data = self.NWB_used.loc[self.NWB_used['trial_id'].isin(test_trials)]
    
    def setup(self, stage=None):
        """ Standardizes spiking input, Min-Max
        Normalizes the target data, and chops
        them into sequences. Loads them into 
        TensorDatasets for DataLoader creation.

        Parameters
        ----------
        stage: Ignore

        """
        
        #Split the dataset into train, val, and test sets
        self.split_dataset()

        #Standardize the spikes (fit only on training set)
        self.spk_train = self.spike_scalar.fit_transform(
            self.train_data.spikes.values
        )

        self.spk_val = self.spike_scalar.transform(self.val_data.spikes.values)

        #Min-Max normalize the velocities (fit only on training set)
        self.vel_train = self.vel_scalar.fit_transform(
            self.train_data[['cursor_velx', 'cursor_vely']].values
        )

        self.vel_val = self.vel_scalar.transform(
            self.val_data[['cursor_velx', 'cursor_vely']].values
        )
        
        #Chop the data into sequences
        self.spk_train = chop_data(
            self.spk_train, 
            self.params['datamodule']['overlap'], 
            self.params['datamodule']['seq_len']
        )

        self.spk_val = chop_data(
            self.spk_val, 
            self.params['datamodule']['overlap'], 
            self.params['datamodule']['seq_len']
        )

        self.vel_train = chop_data(
            self.vel_train, 
            self.params['datamodule']['overlap'], 
            self.params['datamodule']['seq_len']
        )

        self.vel_val = chop_data(
            self.vel_val, 
            self.params['datamodule']['overlap'], 
            self.params['datamodule']['seq_len']
        )
        
        # Define Tensor Datasets for Dataloaders
        self.spk_train = torch.Tensor(self.spk_train)
        self.spk_val = torch.Tensor(self.spk_val)
        self.vel_train = torch.Tensor(self.vel_train)
        self.vel_val = torch.Tensor(self.vel_val)

        self.train_dataset = TensorDataset(self.spk_train, self.vel_train)
        self.val_dataset = TensorDataset(self.spk_val, self.vel_val)

    def train_dataloader(self, shuffle=True):
        """ Creates and returns training
        Dataloader.

        Parameters
        ----------
        shuffle: bool
            Specifies whether to shuffle dataloader
            at the start of each epoch.
        """

        return DataLoader(
            self.train_dataset, 
            batch_size=self.params['datamodule']['batch_size'],
            num_workers=16,
            shuffle=shuffle)

    def val_dataloader(self, shuffle=False):
        """ Creates and returns validation
        Dataloader.

        Parameters
        ----------
        shuffle: bool
            Specifies whether to shuffle dataloader
            at the start of each epoch.
        """
        
        return DataLoader(
            self.val_dataset, 
            batch_size=self.params['datamodule']['batch_size'],
            num_workers=16,
            shuffle=shuffle)
