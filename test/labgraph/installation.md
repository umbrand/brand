## Install CentOS 8
1. Download the x86_64 ISO from [CentOS](https://www.centos.org/download/)
1. Burn the ISO to a flash drive ([balenaEtcher](https://www.balena.io/etcher/?ref=etcher_footer) can do this)
1. Boot to the flash drive. On striate, this is done by pressing F11 during boot and then selecting the drive you want.
1. In the installer menu, ensure that the computer is connected to the network and select the drive you want to install CentOS on. I installed it using the “Server with GUI” configuration, but other configurations may work.

## Install system-level dependecies
Install Git
```
sudo dnf update -y
sudo dnf install git -y
git --version
```
Install gcc
```
sudo dnf group install "Development Tools"
gcc --version
```
Install ZeroMQ
```
sudo dnf install zeromq-devel
```
### Python
Install Python
```
sudo dnf install python3
sudo alternatives --set python /usr/bin/python3
python --version
```
Install Miniconda
```
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh 
conda config --set auto_activate_base false
```
Create conda environment
```
conda create --name labgraph python=3.6.8
```
## Enable remote desktop access (optional)
Install xrdp
```
sudo dnf install epel-release
sudo dnf install xrdp
sudo systemctl enable xrdp --now
sudo systemctl status xrdp
```
Enable access to the RDP port in the firewall
```
sudo firewall-cmd --add-port=3389/tcp --permanent
sudo firewall-cmd --reload
```

## Install LabGraph
Install labgraph
```
pip install labgraph
```
Run the examples in a GUI
```
python -m labgraph.examples.simple_viz
python -m labgraph.examples.simulation
```
Run the test suite with [test_script.sh](https://github.com/facebookresearch/labgraph/blob/master/test_script.sh)
```
export LC_ALL=C.UTF-8
export LANG=en_US.utf-8
sh ./test_script.sh
```
