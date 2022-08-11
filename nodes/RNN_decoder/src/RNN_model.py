#! /usr/bin/env python

import yaml
from torch import nn
import pytorch_lightning as pl

class RNN(pl.LightningModule):
    """ Class to create Recurrent Neural Networks (RNNs) using Pytorch 
    Lightning for BrainGate2 experiments.
    """

    def __init__(self, train=True):
        """ Initializes RNN architecture and parameters.

        Parameters
        ----------
        train : bool, Default: True
            Specifies whether model instantiation is for training or
            real-time implementation. Necessary for predetermination
            of paths and storing hyperparameters.
        """

        super().__init__()

        # Define path to training YAML file
        # Depends on whether training model or not
        if train == True:
            train_yaml = 'src/train_RNN.yaml'
        else:
            train_yaml = './nodes/RNN_decoder/src/train_RNN.yaml'
        
        # Load hyperparameters from YAML file
        with open(train_yaml, 'r') as file:
            self.params = yaml.safe_load(file)

        # Save hyperparameters used to train model
        if train == True:
            self.save_hyperparameters(self.params)

        # ------------ Define model architecture --------------- #

        self.LSTM = nn.LSTM(
            input_size = self.params['model_dim']['input_dim'],
            hidden_size = self.params['model_dim']['hidden_dim'],
            num_layers = self.params['model_dim']['n_layers'],
            batch_first = True
        )

        self.fc = nn.Linear(
            in_features = self.params['model_dim']['hidden_dim'],
            out_features = self.params['model_dim']['output_dim']
        )

        self.Dropout = nn.Dropout(
            p=self.params['model_hparams']['dropout']
        )

    def forward(self, input):
        """ Forward pass of RNN model.

        Parameters
        ----------
        input: torch.tensor
            Tensor of binned spiking data.
            Shape: (batch_size, seq_len, n_features)

        Returns
        -------
        out: torch.tensor
            Target predictions.
            Shape: ()
        """

        # Dropout the input
        input = self.Dropout(input)

        # Dropped out input through LSTM layer(s)
        output, (hn, cn) = self.LSTM(input)

        # return preds from end of sequences
        out = self.fc(output[:, -1, :])

        return out
    