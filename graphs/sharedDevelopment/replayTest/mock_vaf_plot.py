# %%
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm

with matplotlib.rc_context({'font.size': 20}):
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(3)
    bar_width = 0.2
    b1 = ax.bar(x, [0.6, 0.7, 0.8],
                color='black',
                width=bar_width,
                label='Train')
    b2 = ax.bar(x + bar_width, [0.5, 0.6, 0.7],
                color='gray',
                width=bar_width,
                label='Test')

    # Fix the x-axes.
    ax.set_xticks(x + bar_width / 2)
    ax.set_xticklabels([
        'Wiener\nFilter', 'Feedforward\nNeural Network',
        'Recurrent\nNeural Network'
    ])
    plt.ylim([0, 1])
    plt.legend()
    plt.ylabel('$R^2$')
    plt.tight_layout()
    plt.savefig('mock_vaf_plot.pdf')

# %%
