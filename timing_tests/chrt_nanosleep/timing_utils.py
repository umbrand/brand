import os
import csv
import subprocess
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def log_hardware(run_name):
    mem_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')  # e.g. 4015976448
    mem_gib = mem_bytes/(1024.**3)
    command = "lscpu | grep 'Model name' | cut -f 2 -d \":\""
    cpu_model = subprocess.check_output(command, shell=True).strip().decode()
    
    with open('hardware_log.csv','a') as fd:
        writer = csv.writer(fd)
        writer.writerow([run_name, cpu_model, f'{mem_gib:.1f}GB'])
        
def plot_decoder_timing(time_data, type, compare_data=None, test_time=5, y_start_zero=False):
    ''' Plots timing info

    Args:
        time_data (dataframe): 
    '''
    # Set font sizes
    small_font = 14
    med_font = 16
    large_font = 20
    plt.rc('xtick', labelsize=small_font)   # fontsize of the tick labels
    plt.rc('ytick', labelsize=small_font)   # fontsize of the tick labels
    plt.rc('axes', titlesize=med_font)      # fontsize of the axes title
    plt.rc('axes', labelsize=med_font)      # fontsize of the x and y labels
    plt.rc('legend', fontsize=med_font)     # legend fontsize
    plt.rc('figure', titlesize=large_font)  # fontsize of the figure title

    # Create 3 figues and adjust spacing
    fig, axs = plt.subplots(3, figsize=(14, 8), sharex=True)
    fig.tight_layout()
    fig.subplots_adjust(left=0.1, top=0.94, bottom=0.1, hspace=0.3)

    # PUBSUB TEST
    if type == 'PUB_SUB':
        title = f'Publisher Subscriber Latency Analysis ({test_time} min)' if (
            compare_data is None
        ) else f'Publisher Subscriber Latency Comparison vs Baseline ({test_time} min)'

        # publisher latency
        axs[0].set_title('Intersample Latency for publisher (1000hz, ???????????????????ch)')
        pub_latency = np.diff(time_data['ts_pub'] * 1000, n=1)

        # redis latency
        axs[1].set_title('Redis Transmission Latency')
        redis_latency = (time_data['ts_sub'] - time_data['ts_pub']) * 1000

        # subscriber latency
        axs[2].set_title(f'{type} Intersample Latency for subscriber')
        sub_latency = np.diff(time_data['ts_sub'] * 1000, n=1)

        # Data array for easy looping
        data = [pub_latency, redis_latency, sub_latency]

    # DECODER TEST
    elif type in ['OLE', 'RNN', 'NDT']:
        # Create figure title and shared axis labels
        title = f'{type} Decoder Latency Analysis ({test_time} min)' if (
            compare_data is None
        ) else f'{type} Decoder Latency Comparison vs Basline ({test_time} min)'

        # func_generator latency
        axs[0].set_title('Intersample Latency for func_generator (200hz, 256ch)')
        fg_latency = np.diff(time_data['ts_in'] * 1000, n=1)

        # redis latency
        axs[1].set_title('Redis Transmission Latency')
        redis_latency = (time_data['ts_read'] - time_data['ts_in']) * 1000

        # ndt node latency
        axs[2].set_title(f'{type} Node Latency')
        decoder_latency = (time_data['ts_add'] - time_data['ts_read']) * 1000

        # Data array for easy looping
        data = [fg_latency, redis_latency, decoder_latency]

    # Implement other types of tests here!
    else:
        print('UNKNOWN TEST TYPE')
        return

    # Set titles
    fig.text(0.5, 1.0, title, ha='center', fontsize=large_font)
    fig.text(0.5, 0.04, 'Experiment Duration (min)', ha='center', fontsize=med_font+1,)
    fig.text(0.04, 0.5, 'Latency (ms)', va='center', rotation='vertical', fontsize=med_font+1)

    # Plot user data to compare with baseline
    if compare_data is not None:
        if type == 'PUB_SUB':
            compare_pub_latency = np.diff(compare_data['ts_pub'] * 1000, n=1)
            compare_redis_latency = (compare_data['ts_sub'] - compare_data['ts_pub']) * 1000
            compare_sub_latency = np.diff(compare_data['ts_pub'] * 1000, n=1)
            compare = [compare_pub_latency, compare_redis_latency, compare_sub_latency]

        elif type in ['OLE', 'RNN', 'NDT']:
            compare_fg_latency = np.diff(compare_data['ts_in'] * 1000, n=1)
            compare_redis_latency = (compare_data['ts_read'] - compare_data['ts_in']) * 1000
            compare_decoder_latency = (compare_data['ts_add'] - compare_data['ts_read']) * 1000
            compare = [compare_fg_latency, compare_redis_latency, compare_decoder_latency]

        baseline_patch = mpatches.Patch(color='blue', label='Baseline')
        compared_patch = mpatches.Patch(color='red', label='Your Test')
            


    # Divide data into 5 ticks on x axis 
    data_div = int(len(time_data['ts_read'])/5)

    # Loop through plots, plot latency, update axis info, and print stats
    for idx, ax in enumerate(axs):
        ax.plot(data[idx], color='tab:blue')

        if compare_data is not None:
            ax.plot(compare[idx], color='tab:red')
            ax.legend(handles=[baseline_patch, compared_patch])
            ax.set_title(  
                f'μ={compare[idx].mean():.3f}ms, σ={compare[idx].std():.3f}ms', 
                loc='left', 
                color='tab:red'
            )
            
        ax.set_xticks([data_div * i for i in range (6)])
        ax.set_xticklabels(np.arange(0, test_time + (test_time//5), test_time//5))
        ax.set_title(
            f'μ={data[idx].mean():.3f}ms, σ={data[idx].std():.3f}ms', 
            loc='right', 
            color='black' if compare_data is None else 'tab:blue'
        )

        # Start from 0 on y axis
        if y_start_zero:
            ax.set_ybound(0, data[idx].max()+(data[idx].max()*0.2))

    # Save the plot
    fig.savefig(
        f'plots/{type}_{datetime.now().strftime("%m%d%y_%H%M")}.png', 
        facecolor='white', 
        transparent=False, 
        bbox_inches="tight"
    )