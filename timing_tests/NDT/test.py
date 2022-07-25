from tqdm import tqdm
import time

old_time = 0

# [default: '{l_bar}{bar}{r_bar}'], 
# where l_bar='{desc}: {percentage:3.0f}%|' and 
# r_bar='| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, ' '{rate_fmt}{postfix}]' 
# Possible vars: l_bar, bar, r_bar, n, n_fmt, total, total_fmt, 
# percentage, elapsed, elapsed_s, ncols, nrows, desc, unit, rate, 
# rate_fmt, rate_noinv, rate_noinv_fmt, rate_inv, rate_inv_fmt, postfix, 
# unit_divisor, remaining, remaining_s, eta. 
# Note that a trailing ": " is automatically removed after {desc} if the latter is empty.



bar = tqdm(total=300, bar_format='{l_bar}{bar}| {elapsed} / '+str(test_time)+':00  ')
timer = time.time()
while int(time.time() - timer) < 300:
        current_time = int(time.time() - timer)
        bar.update(current_time - old_time)
        old_time = current_time