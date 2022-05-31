# Setup
## Installing the PREEMPT_RT Patch
### System Information
Example:
Kernel version (via `uname -msr`): `Linux 4.15.0-101-generic x86_64`
Ubuntu version (via `lsb_release -a`):
```
Distributor ID:	Ubuntu
Description:	Ubuntu 18.04.4 LTS
Release:	18.04
Codename:	bionic
```

### Downloading the patch
Find the most recent long-term kernel [here](kernel.org). Go to the `PREEMPT_RT` project and find the most recent `rt` patch for the long-term kernel version [here](https://mirrors.edge.kernel.org/pub/linux/kernel/projects/rt/). Note that all three version numbers of the Linux kernel must match all three numbers of the `rt` patch (except the `rtXX`), so find the matching Linux kernel version [here](https://mirrors.edge.kernel.org/pub/linux/kernel/). For example, If the most recent long-term Linux kernel version is `5.15.44` but the `rt` project only has `5.15.43`, then you must use the Linux kernel for version `5.15.43` too. Be sure to download the `.xz` file extension for the Linux kernel and the `.patch.xz` extension for the `rt` patch.
```
cd
mkdir -p Installs/rt-kernel
cd Installs/rt-kernel
wget https://mirrors.edge.kernel.org/pub/linux/kernel/v5.x/linux-5.15.43.tar.xz  # kernel
wget https://mirrors.edge.kernel.org/pub/linux/kernel/projects/rt/5.15/older/patch-5.15.43-rt45.patch.xz # patch
```

### Compiling and Installing the Kernel
Follow the steps below based on this [blog post](https://chenna.me/blog/2020/02/23/how-to-setup-preempt-rt-on-ubuntu-18-04/).

1. Install dependencies.
    ```
    sudo apt install build-essential git libssl-dev libelf-dev flex bison dwarves zstd libncurses-dev
    ```
1. Extract the archive and apply the patch.
    ```
    xz -cd linux-5.15.43.tar.xz | tar xvf -
    cd linux-5.14.43
    xzcat ../patch-5.15.43-rt45.patch.xz | patch -p1
    ```
1. Copy the old configuration as the basis for the new kernel.
    ```
    cp /boot/config-5.13.0-44-generic .config # example
    make menuconfig
    ```
1. Under `General setup --->` > `Preemption Model (Fully Preemptible Kernel (Real-Time)) --->` choose `Fully Preemptible Kernel (Real-Time)`. Hit `Exit` to go back to the top config menu.
1. Under `Cryptographic API (CRYPTO [-y])` > `Certificates for signature checking` (last item in the list) > `(debian/canonical-certs.pem) Additional X.509 keys for default system keyring` (or something like that in the parentheses), delete the string in the field.
1. In the same menu under `(debian/canonical-certs.pem) X.509 certificates to be preloaded into the system blacklist keyring` (or something like that in the parentheses), delete the string in the field.
1. Hit `Save`, then `Exit` all the way out of `menuconfig`.
1. Compile the new kernel. Note the `-j` option runs parallel jobs, so increase the number to speed up the process, but too many can hang the system.
    ```
    make -j8 all; make -j8 modules_install; sudo make -j8 install
    ```
1. Update the `ramdisk` initialization options based on [this Stack Exchange post](https://unix.stackexchange.com/a/671382):
    ```
    nano /etc/initramfs-tools/initramfs.conf
    ```
1. Update the `MODULES` line to say:
    ```
    MODULES=dep
    ```
1. Regenerate the `ramdisk` initialization options.
    ```
    update-initramfs -c -k 5.15.43-rt45
    ```

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
