# Setup
## Installing the PREEMPT_RT Patch
### System Information
Kernel version (via `uname -msr`): `Linux 4.15.0-101-generic x86_64`   
Ubuntu version (via `lsb_release -a`):
```
Distributor ID:	Ubuntu
Description:	Ubuntu 18.04.4 LTS
Release:	18.04
Codename:	bionic
```
### Downloading the patch
There is no RT patch available for kernel version `4.15`, so we will have to use another kernel version from [here](https://mirrors.edge.kernel.org/pub/linux/kernel/) and patch version from [here](https://mirrors.edge.kernel.org/pub/linux/kernel/projects/rt/). I selected version kernel version `5.4.40` and its corresponding `preempt_rt` patch because that is the latest version with long-term support.
```
wget https://mirrors.edge.kernel.org/pub/linux/kernel/v5.x/linux-5.4.40.tar.xz  # kernel
wget https://mirrors.edge.kernel.org/pub/linux/kernel/projects/rt/5.4/older/patch-5.4.40-rt24.patch.xz  # patch
```

### Compiling and Installing the Kernel
Follow the instructions in this [blog post](https://chenna.me/blog/2020/02/23/how-to-setup-preempt-rt-on-ubuntu-18-04/) to compile and install the kernel.
#### Installation Notes
- The `make -j8 deb-pkg` step took about 30 minutes to complete on `SNEL-Rig1-A` (Intel Core i7-4790K CPU @ 4.00GHz).
- After running the `dpkg -i` command, you may see warnings about missing firmware. Follow the instructions [here](https://askubuntu.com/questions/832524/possible-missing-frmware-lib-firmware-i915) to install that missing firmware.

### Testing the Kernel
#### Installing the tests
Dependencies:
```
apt-get install libnuma-dev  # for cyclictest
```
Tests:
```
git clone git://git.kernel.org/pub/scm/utils/rt-tests/rt-tests.git  # cyclictest
cd rt-tests/
git checkout stable/v1.0
make all
```
#### Breaking down the [OSADL](http://www.osadl.org) `cyclictest` command
```
cyclictest -l100000000 -m -Sp99 -i200 -h400 -q
```
```
-l100000000 = 1e8 loops
-m  = memlock
-S = use the standard testing options for SMP systems
-p99 = set the realtime priority to 99
-i200 = set base interval of the thread to 200 microseconds
-h400 = dump latency histogram to stdout. 400 microseconds is the max latency time to track.
-q = Run the tests quietly and print only a summary on exit.
```
#### Running the tests:
Follow the instructions [here](http://www.osadl.org/Create-a-latency-plot-from-cyclictest-hi.bash-script-for-latency-plot.0.html) to make a latency plot.
