# BRANDS RNN Decoder Node

#### Author: Bareesh Bhaduri

Recurrent Neural Network (RNN) node to use in BrainGate2 experiments at Emory University. If you haven't already, read through the documentation for BRANDS (insert link later) to understand how this node fits into the BRANDS pipeline.

Shown below is an overview of the node directory structure:

    RNN_decoder
        |
        |____ src #folder that holds all model scripts
        |
        |____ RNN_decoder.py #Real-time inference script
        |
        |____ RNN_decoder.yaml # BRANDS Node YAML
        |
        |____ train_RNN.py #model training script

## Training

To create and train an RNN model, navigate to the following directory on your machine:  
`Data/<Participant>/Session<num>/code/brand-modules/brand-emory/nodes/RNN_decoder`

After traveling to this directory, complete the following items to start the training process:
* Define the model parameters in `src/train_RNN.yaml` (see below for details)
* Run the command `./train_RNN.py` from the `RNN_decoder` folder, not the `src` folder.

### Training YAML File

Below is an explanation of each parameter defined in the `train_RNN.yaml` file:

    callbacks:
        early_stop_patience: #number of non-improving epochs before stopping training
        scheduler_patience: #number of non-improving epochs before lowering learning rate
    datamodule:
        batch_size: #batch size in dataloaders
        overlap: #number of overlapping bins between chopped sequences
        seq_len: #length of sequences in chops
    model_dim:
        hidden_dim: #number of hidden units in LSTM layer(s)
        input_dim: #number of channels in the input data
        n_layers: #number of LSTM layers
        output_dim: #number of targets in the target data
    model_hparams:
        dropout: #float value for probability of dropout in dropout layer
        gauss_noise: #boolean value to add/not add noise to input data
        learn_rate: #initial learning rate for training
        weight_decay: #parameter in optimizer for L2 regularization
    real-time:
        saved_scalars: #path to saved scalar objects (updates after every training run)
        saved_weights: #path to saved model weights (updates after every training run)
    training:
        bin_size: #desired bin size of the data
        data_dir: #path to training data
        log_name: #name for Tensorboard log (updates by date)
        log_pth: #path to store TensorBoard log to
        max_epochs: #max number of epochs to train for
        n_steps: #interval of steps to log for
        save_pth: #path to save model weights and scalars to

    RedisStreams:
    Inputs:
        <input_stream_name>:
            type: 
            name: 
            label: 
    Outputs:
        <output_stream_name>:
            sync: 
            type: 
            name: 
            label:

If the `RedisStreams` section of the YAML file is unfamiliar to you, see documentation about Data Alignment here (insert link later). 

## Real-time Inference

To run real-time model inference with the RNN using supervisor, add the RNN decoder node to your Graph YAML file. Below is a template of what you should define:

    nodes:
        - name:         RNN_decoder
          version:      0.0
          nickname:     
          stage:        main
          module:       ../brand-modules/brand-emory
          redis_inputs:                 []
          redis_outputs:                []
          run_priority:                 
          parameters:                   
            n_features:             # insert value defined when training
            n_targets:              # insert value defined when training
            seq_len:                # insert value defined when training
            model_pth:              ../brand-modules/brand-emory/nodes/RNN_decoder/src/train_RNN.yaml
            log:                    INFO


**Note**: The `model_pth` parameter defines the directory to the `train_RNN.yaml` file in order to find the model weights and scalars for inference. As stated above, the paths to the RNN weights and scalars update in the `train_RNN.yaml` file after every training run. Therefore, **DO NOT** change this unless you wish to use weights/scalars that **don't** correspond to the most recent training run.
