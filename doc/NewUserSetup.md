# How to add a new user for BRAND use

## Create a new user

You can create a new user either locally or over SSH. Note that SSH may not be enabled on a new computer.

First, via a user with sudo permissions, add a new user, and fill in the prompts as desired:
```
sudo adduser <new_user>
```

This user will need sudo permissions later, so before logging into the user, give it sudo permissions.
```
sudo usermod -aG sudo <new_user>
```

Now, log out of the current user and log into the new user.

## Set up conda

### Install conda

Next, you have to recreate the conda environment. To do so, create an `Installs` directory:
```
mkdir Installs
```
Then, download the latest [miniconda installer](https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html) to `Installs`. Download the newest version for Python 3.8, or whatever is the current version of Python being used for BRAND.

Now create a new folder to store miniconda and other installed software:
```
mkdir lib
```

Now install miniconda:
```
cd Installs
bash Miniconda3-latest-Linux-x86_64.sh
```
When prompted, set the install directory to be `/home/<new_user>/lib/miniconda3`.

If prompted about whether to initialize miniconda, enter `yes`.

Note that the following conda-related steps do not need to be run if you intend to install BRAND.

### Recreating an environment from a pre-existing one

When creating a new user, one may want to build an identical conda environment and its packages to a pre-existing one from a different user. To do so, first log into the user account containing the original conda environment and activate the environment.
```
conda activate <env>
conda env export > <env>_env.yml
```

Switch back to the `new_user` account, create a new environment, copy the `<env>_env.yml` file to `/home/<new_user>/Installs`, then install it.
```
cd
cp /path/to/<env>_env.yml /home/<new_user>/Installs
conda env create -f Installs/<env>_env.yml
```

### Installing missing packages

Exporting a conda environment only exports packages that can be installed by `pip`. Packages that cannot be installed by pip need to be installed manually.

# Installing BRAND

Create a projects directory into which we will store BRAND, then clone the [repository](https://github.com/snel-repo/realtime_rig_dev.git).
```
cd
mkdir Projects
cd Projects
git clone https://github.com/snel-repo/realtime_rig_dev.git
```

Now build BRAND by following the instructions in `Projects/realtime_rig_dev/README.md`, providing the password as needed.