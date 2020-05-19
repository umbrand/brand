# %%
import copy
import cProfile
import os
import time
import gc

import h5py
import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp
from tensorflow.keras.utils import Progbar

from lfads_tf2.defaults import get_cfg_defaults
from lfads_tf2.models import LFADS
from lfads_tf2.tuples import DecoderInput, SamplingOutput
from lfads_tf2.utils import (load_data, load_posterior_averages,
                             restrict_gpu_usage)

tfd = tfp.distributions
gc.disable()  # disable garbage collection

# tf.debugging.set_log_device_placement(True)
restrict_gpu_usage(gpu_ix=0)
# %%
# restore the LFADS model
cfg_path = os.path.join(os.path.abspath('./'), 'lorenz.yaml')
cfg = get_cfg_defaults()
cfg.merge_from_file(cfg_path)
cfg.freeze()

# model = LFADS(model_dir=os.path.expanduser(cfg.TRAIN.MODEL_DIR))
# model.restore_weights()

model = LFADS(cfg_path=cfg_path)
model.train()  # train a dummy model for 4 epochs

# %%
# Load the spikes and the true rates
train_truth, valid_truth = load_data(cfg.TRAIN.DATA.DIR,
                                     prefix=cfg.TRAIN.DATA.PREFIX,
                                     signal='truth')[0]

# %%
loop_times = []


def sample_and_average(model,
                       n_samples=50,
                       batch_size=64,
                       ps_filename='posterior_samples.h5',
                       save=True,
                       merge_tv=False):
    """Saves rate estimates to the 'model_dir'.

    Performs a forward pass of LFADS, but passes multiple 
    samples from the posteriors, which can be used to get a 
    more accurate estimate of the rates. Saves all output 
    to posterior_samples.h5 in the `model_dir`.

    Parameters
    ----------
    n_samples : int, optional
        The number of samples to take from the posterior 
        distribution for each datapoint, by default 50.
    batch_size : int, optional
        The number of samples per batch, by default 128.
    ps_filename : str, optional
        The name of the posterior sample file, by default
        'posterior_samples.h5'. Ignored if `save` is False.
    save : bool, optional
        Whether or not to save the posterior sampling output
        to a file, if False will return a tuple of 
        SamplingOutput. By default, True.
    merge_tv : bool, optional
        Whether to merge training and validation output, 
        by default False. Ignored if `save` is True.

    Returns
    -------
    SamplingOutput
        If save is True, return nothing. If save is False, 
        and merge_tv is false, retun SamplingOutput objects 
        training and validation data. If save is False and 
        merge_tv is True, return a single SamplingOutput 
        object.

    """
    output_file = os.path.join(model.cfg.TRAIN.MODEL_DIR, ps_filename)

    try:
        # remove any pre-existing posterior sampling file
        os.remove(output_file)
        model.lgr.info(
            f"Removing existing posterior sampling file at {output_file}")
    except OSError:
        pass

    if not model.is_trained:
        model.lgr.warn("Performing posterior sampling on an untrained model.")

    # define merging and splitting utilities
    def merge_samp_and_batch(data, batch_dim):
        """ Combines the sample and batch dimensions """
        return tf.reshape(data, [n_samples * batch_dim] +
                          tf.unstack(tf.shape(data)[2:]))

    def split_samp_and_batch(data, batch_dim):
        """ Splits up the sample and batch dimensions """
        return tf.reshape(data, [n_samples, batch_dim] +
                          tf.unstack(tf.shape(data)[1:]))

    # ========== POSTERIOR SAMPLING ==========
    # perform sampling on both training and validation data
    global loop_times
    loop_times = []
    for prefix, dataset in zip(['train_', 'valid_'],
                               [model._train_ds, model._val_ds]):
        data_len = len(model.train_tuple.data) if prefix == 'train_' else len(
            model.val_tuple.data)

        # initialize lists to store rates
        all_outputs = []
        model.lgr.info(
            "Posterior sample and average on {} segments.".format(data_len))
        if not model.cfg.TRAIN.TUNE_MODE:
            pbar = Progbar(data_len, width=50, unit_name='dataset')

        def process_batch():
            # unpack the batch
            data, _, ext_input = batch

            # pass data through low-dim readin for alignment compatibility
            if (model.cfg.MODEL.READIN_DIM > 0
                    and not model.cfg.MODEL.ALIGN_MODE):
                data = model.lowd_readin(data)

            # for each chop in the dataset, compute the initial conditions
            # distribution
            ic_mean, ic_stddev, ci = model.encoder.graph_call(data)
            ic_post = tfd.MultivariateNormalDiag(ic_mean, ic_stddev)

            # sample from the posterior and merge sample and batch dimensions
            ic_post_samples = ic_post.sample(n_samples)
            ic_post_samples_merged = merge_samp_and_batch(
                ic_post_samples, len(data))

            # tile and merge the controller inputs and the external inputs
            ci_tiled = tf.tile(tf.expand_dims(ci, axis=0),
                               [n_samples, 1, 1, 1])
            ci_merged = merge_samp_and_batch(ci_tiled, len(data))
            ext_tiled = tf.tile(tf.expand_dims(ext_input, axis=0),
                                [n_samples, 1, 1, 1])
            ext_merged = merge_samp_and_batch(ext_tiled, len(data))

            # pass all samples into the decoder
            dec_input = DecoderInput(ic_samp=ic_post_samples_merged,
                                     ci=ci_merged,
                                     ext_input=ext_merged)
            output_samples_merged = model.decoder.graph_call(dec_input)

            # average the outputs across samples
            output_samples = [
                split_samp_and_batch(t, len(data))
                for t in output_samples_merged
            ]
            output = [np.mean(t, axis=0) for t in output_samples]

            # aggregate for each batch
            non_averaged_outputs = [
                ic_mean.numpy(),
                tf.math.log(ic_stddev**2).numpy(),
            ]
            all_outputs.append(output + non_averaged_outputs)
            if not model.cfg.TRAIN.TUNE_MODE:
                pbar.add(len(data))

        # ran_profile = False
        last_time = time.time()
        for batch in dataset.batch(batch_size):
            process_batch()
            loop_times.append(time.time() - last_time)
            # if ran_profile is False:
            #     prof = cProfile.Profile(timeunit=1e-6)
            #     prof = cProfile.runctx('process_batch()',
            #                            globals(),
            #                            locals(),
            #                            filename='ps_profile')
            #     ran_profile = True
            last_time = time.time()

        # collect the outputs for all batches and split them up into the
        # appropriate variables
        all_outputs = list(zip(*all_outputs))  # transpose the list / tuple
        all_outputs = [np.concatenate(t, axis=0) for t in all_outputs]
        (rates, co_means, co_stddevs, factors, gen_states, gen_init,
         gen_inputs, con_states, ic_post_mean, ic_post_logvar) = all_outputs

        # return the output in an organized tuple
        samp_out = SamplingOutput(
            rates=rates,
            factors=factors,
            gen_states=gen_states,
            gen_inputs=gen_inputs,
            gen_init=gen_init,
            ic_post_mean=ic_post_mean,
            ic_post_logvar=ic_post_logvar,
            ic_prior_mean=model.ic_prior_mean.numpy(),
            ic_prior_logvar=model.ic_prior_logvar.numpy())

        # writes the output to the a file in the model directory
        with h5py.File(output_file, 'a') as hf:
            output_fields = list(samp_out._fields)
            for field in output_fields:
                hf.create_dataset(prefix + field,
                                  data=getattr(samp_out, field))
    try:
        # copy the training and validation indices if they exist
        train_inds, valid_inds = load_data(model.cfg.TRAIN.DATA.DIR,
                                           prefix=model.cfg.TRAIN.DATA.PREFIX,
                                           signal='inds')[0]
        with h5py.File(output_file, 'a') as hf:
            hf.create_dataset('train_inds', data=train_inds)
            hf.create_dataset('valid_inds', data=valid_inds)
    except AssertionError:
        pass

    if not save:
        # If saving is disabled, load from the file and delete it
        output = load_posterior_averages(model.cfg.TRAIN.MODEL_DIR,
                                         merge_tv=merge_tv)
        os.remove(output_file)
        return output


# %%
# perform posterior sampling, then merge the chopped segments
n_samples = 1
sample_and_average(model, batch_size=1, n_samples=n_samples)

# calculate loop times
p_loop_times = copy.copy(loop_times)  # processed loop times
del p_loop_times[0]  # first iteration is slower due to graph initialization
p_loop_times = np.array(p_loop_times) * 1e3

# %%
message = ('Posterior sample and average latency: '
           '{:.1f} +- {:.1f}, Range: {:.1f} ({:d}th seq) to '
           '{:.1f} ({:d}th seq), Sequence Length: {:d} bins').format(
               np.mean(p_loop_times), np.mean(np.abs(np.diff(p_loop_times))),
               np.min(p_loop_times), np.argmin(p_loop_times),
               np.max(p_loop_times), np.argmax(p_loop_times),
               model.cfg.MODEL.SEQ_LEN)
print(message)

# %%
edges = np.arange(start=np.floor(np.min(p_loop_times)),
                  stop=np.ceil(np.max(p_loop_times)),
                  step=1)
plt.figure(figsize=(12, 6))
plt.subplot(1, 2, 1)
plt.hist(p_loop_times, bins=edges, edgecolor='white', linewidth=1)
plt.xlabel(
    'Latency per {:d}-bin sequence (in ms)\n'.format(model.cfg.MODEL.SEQ_LEN) +
    'Mean: {:.1f}, Jitter: {:.1f}, Min: {:.1f}, Max: {:.1f}'.format(
        np.mean(p_loop_times), np.mean(np.abs(np.diff(p_loop_times))),
        np.min(p_loop_times), np.max(p_loop_times)))
plt.ylabel('Batches')
plt.title('Latency Distribution')

plt.subplot(1, 2, 2)
plt.plot(p_loop_times)
plt.xlabel('Data Segment')
plt.ylabel('Latency (in ms)')
plt.title('Latencies during Execution')

plt.suptitle(('Latencies of {:d}-sample Posterior Sample and Average'
              ' for 29-channel Lorenz Data').format(n_samples))
plt.savefig('ps_latencies_{:d}sample.png'.format(n_samples))

# %%
