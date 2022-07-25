#! /usr/bin/env python
import math
import copy
import torch
from torch import nn
import pytorch_lightning as pl
from torch.nn import functional as F
from torch.nn import ModuleList, Module
from torch.nn.parameter import Parameter
from torch.nn import TransformerEncoderLayer
from torch.nn.init import constant_, xavier_uniform_
from torch.nn.modules.linear import NonDynamicallyQuantizableLinear as NDQL

class ScaleNorm(Module):
    '''ScaleNorm from T-fixup'''
    def __init__(self, scale, eps=1e-5):
        super(ScaleNorm, self).__init__()
        self.scale = nn.Parameter(torch.tensor(scale))
        self.eps = eps

    def forward(self, x):
        norm = self.scale / torch.norm(x, dim=-1, keepdim=True).clamp(min=self.eps)
        return x * norm

def get_attn_mask(params):
    ones = torch.ones(params['seq_len'], params['seq_len'])
    forw_mask = (torch.triu(ones, diagonal=-params['context_forward']) == 1).transpose(0, 1)
    back_mask = (torch.triu(ones, diagonal=-params['context_backward']) == 1)
    mask = (forw_mask & back_mask).float()
    mask = mask.masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
    return mask

def get_norm(input_dim, norm):
    if norm == 'layer':
        return nn.LayerNorm(input_dim)
    elif norm == 'scale':
        return ScaleNorm(input_dim ** 0.5)
    elif norm == 'None':
        return None

class MHA(Module):
    def __init__(self, config):
        super(MHA, self).__init__()
        self.config = config

        # If using undivided attention, each head needs 'input_dim' dimensions
        self.packed_dim_size = config['input_dim'] * config['n_heads'] if (
            config['undivided_attn']
        ) else config['input_dim']

        # MHA uses a packed tensor, Queries Keys and Values all share the same weight matrix
        self.in_proj_weight = Parameter(torch.empty((3 * self.packed_dim_size, config['input_dim'])))
        self.in_proj_bias = Parameter(torch.empty(3 * self.packed_dim_size))
        self.out_proj = NDQL(self.packed_dim_size, config['input_dim'])

        # Init QKV weights and all biases
        xavier_uniform_(self.in_proj_weight)
        constant_(self.in_proj_bias, 0.)
        constant_(self.out_proj.bias, 0.)

    def forward(self, src, attn_mask=None):
        # Use the same weight matrix then seperate 
        self.q, self.k, self.v = torch._C._nn.linear(src, self.in_proj_weight, self.in_proj_bias).chunk(3, dim=-1)

        # If using undivided attention the view shape is [T x (B * n_heads) x N]
        self.view_shape = (src.shape[0], src.shape[1] * self.config['n_heads'], src.shape[2]) if (
            bool(self.config['undivided_attn'])
        ) else (
            # If using standard MHA the view shape is [T x (B * n_heads) x (N // n_heads)]
            (src.shape[0], src.shape[1] * self.config['n_heads'], src.shape[2] // self.config['n_heads'])
        )
        self.q = self.q.contiguous().view(*self.view_shape).transpose(0, 1) / math.sqrt(self.view_shape[2])
        self.k = self.k.contiguous().view(*self.view_shape).transpose(0, 1)
        self.v = self.v.contiguous().view(*self.view_shape).transpose(0, 1)

        # Create the attention matrix [T x T]
        self.attn = torch.bmm(self.q, self.k.transpose(-2, -1))

        # Restrict how far in past / future each timestep can attend to
        if attn_mask is not None:
            self.attn += attn_mask

        # Apply softmax and dropout to attention matrix    
        self.attn = F.softmax(self.attn, dim=-1)
        if self.training:
            self.attn = F.dropout(self.attn, p=self.config['dropout_mid_attn'] )
        
        # Multiply attention matrix (QK) and values (V)
        self.attn_output = torch.bmm(self.attn, self.v).transpose(0, 1)
        self.attn_output = self.attn_output.contiguous().view(src.shape[0] * src.shape[1], self.packed_dim_size)

        # Project to proper size ([T x B x N]) and return
        return torch._C._nn.linear(self.attn_output, self.out_proj.weight, self.out_proj.bias).view(*src.shape)


class EncoderLayer(TransformerEncoderLayer):
    def __init__(self, config):
        super().__init__(
            config['input_dim'], 
            nhead=1,
            dim_feedforward=config['hidden_size'],
            activation=config['activation']
        )
        self.config = config

        # Override standard MHA for our custom module
        self.self_attn = MHA(config)

        # Override norms to allow for ScaleNorm use
        self.norm1 = get_norm(config['input_dim'], config['mha_norm'])
        self.norm2 = get_norm(config['input_dim'], config['mlp_norm'])

        # Override Dropout to change probability at different stages
        self.dropout = nn.Dropout(config['dropout_post_attn'])
        self.dropout1 = nn.Dropout(config['dropout_mid_mlp'])
        self.dropout2 = nn.Dropout(config['dropout_post_mlp'])

        # T-fixup
        if config['t_fixup']:
            temp_state_dic = {}
            for name, param in self.named_parameters():
                if name in ["linear1.weight", "linear2.weight", "self_attn.out_proj.weight"]:
                    temp_state_dic[name] = param * (0.67 * (config['n_layers']) ** (- 1. / 4.))
            for name in self.state_dict():
                if name not in temp_state_dic:
                    temp_state_dic[name] = self.state_dict()[name]
            self.load_state_dict(temp_state_dic)

    def forward(self, src, attn_mask=None):
        # MHA
        self.residual = src # skip connection
        if self.config['pre_norm']: # pre norm
            if self.training:
                src = self.residual + self.dropout(self.self_attn(self.norm1(src), attn_mask))
            else:
                src = self.residual + self.self_attn(self.norm1(src), attn_mask)
        else: # post norm
            src = self.norm1(self.residual + self.dropout(self.self_attn(src, attn_mask)))

        # MLP
        self.residual = src # skip connection
        if self.config['pre_norm']: # pre norm
            if self.training:
                src = self.residual + self.dropout2(self.linear2(self.dropout1(self.activation(self.linear1(self.norm2(src))))))
            else:
                src = self.residual + self.linear2(self.activation(self.linear1(self.norm2(src))))
        else: # post norm
            src = self.norm2(self.residual + self.dropout2(self.linear2(self.dropout1(self.activation(self.linear1(src))))))

        return src


class Encoder(Module):
    def __init__(self, config):
        super().__init__()
        # Copy multiple EncoderLayers to create a single encoder
        self.layers = ModuleList([copy.deepcopy(EncoderLayer(config)) for i in range(config['n_layers'])])
        
        # Normalization to be used after running through all EncoderLayers
        self.norm = get_norm(config['input_dim'], config['final_norm'])

    def forward(self, src, attn_mask=None):
        # Run through each EncoderLayer's forward pass
        for layer in self.layers:
            src = layer(src, attn_mask)

        # Final normalization
        if self.norm is not None:
            src = self.norm(src)

        return src


class NDT(pl.LightningModule):

    def __init__(self, config, train_mean, train_std):
        super().__init__()

        self.config = config

        # Set Seeds
        torch.random.manual_seed(self.config['seed'])
        torch.backends.cudnn.deterministic = True

        self.train_mean = train_mean
        self.train_std = train_std

        # Define model architecture
        self.encoder = Encoder(self.config)
        self.decoder = nn.Linear(self.config['input_dim'], self.config['input_dim'])

        # Init Decoder
        self.decoder.bias.data.zero_()
        self.decoder.weight.data.uniform_(-self.config['decoder_initrange'], self.config['decoder_initrange'])

        # Init Dropout
        self.embedding_dropout = nn.Dropout(p=self.config['dropout_embedding'])
        self.rates_dropout = nn.Dropout(p=self.config['dropout_rates'])

        # Init Positional Embedding
        pe = torch.zeros(self.config['seq_len'], self.config['input_dim'])
        self.register_buffer('pe', torch.arange(0, self.config['seq_len'], dtype=torch.long).unsqueeze(1))
        self.pos_embedding = nn.Embedding(self.config['seq_len'], self.config['input_dim'])
        
        # Init vars for forward call and MLM
        self.scale = math.sqrt(self.config['input_dim'])
        self.loss_fnc = nn.PoissonNLLLoss(log_input=True, full=True, reduction='none')
        self.register_buffer("attn_mask", get_attn_mask(self.config))
        self.zero_prob_mask, self.random_prob_mask, self.loss_prob_mask = None, None, None

        self.relu = nn.ReLU()

    
    def optimizer_zero_grad(self, epoch, batch_idx, optimizer, optimizer_idx):
        optimizer.zero_grad(set_to_none=True)

    def forward(self, input, labels=None):
        # torch.clamp(input, 0.0, self.train_max, out=input)
        
        input = (input - self.train_mean) / self.train_std

        # Scale and re-order dimensions [B x T x N] -> [T x B x N]]
        input = input.permute(1, 0, 2) * self.scale

        # Add Positional Embedding then dropout
        input += self.pos_embedding(self.pe)
        if self.training:
            input = self.embedding_dropout(input)

        # Pass through transformer encoder and dropout some rates
        input = self.encoder(input, self.attn_mask)
        if self.training:
            input = self.rates_dropout(input)

        # Pass through decoder and re-order dimensions [T x B x N] ->  [B x T x N], then exponentiate
        pred_rates = self.decoder(input)
        pred_rates = pred_rates.permute(1, 0, 2).exp()

        # If no labels are given then only return rates
        if labels == None: return pred_rates

        # Else, Compute loss only on marked indices and return
        loss = self.loss_fnc(pred_rates.log(), labels)
        loss = loss.mean()

        return loss, pred_rates

    
