# Emory real-time rig
## Building
### Requirements
* Host Machine Running Ubuntu 18.04
* Nvidia GPU with Compute Capabilities > ?
* CUDA 10.0

### Environment Setup and Make
`bootstrap.sh` is provided to automate the environment setup. It installs debian pkg dependencies using `apt-get` and creates the real-time conda environment (rt), which is defined by `environment.yaml`. [redis](https://github.com/antirez/redis) and [hiredis](https://github.com/redis/hiredis) have been included as submodules, which also get initialized by `bootstrap.sh`. After running bootstrap you simply need to run `make` at the project root. This will build all the project binaries, including submodule dependencies, and output them to `bin/`. Be sure to activate the conda env before running make as Makefiles dependent on cython require it.
```
./boostrap.sh
conda activate rt
make
```
