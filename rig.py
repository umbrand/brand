

# This is the main script to setup and run the real-time rig


#################################################
## Imports
#################################################

import sys
import cmd
import os
import yaml

#################################################
## Global variables
#################################################

SESSION_PATH = 'session/'
RUN_PATH     = 'run/'
MODULE_PATH  = 'proc/'
BIN_PATH     = 'bin/'
VERSION      = 0.1

#################################################
## Helpers
#################################################

# Return a list of the folders in the directory
def folders_list(filepath):
    for (path, dirs, files) in os.walk(filepath):
        return dirs

# The rig has a characteristic folder structure. It expects
# To find a few folders. Check if this is a nice filestructure
def is_correct_rig_folder_structure():
    folder_list = ['lib','proc','session']
    for folder in folder_list:
        if not os.path.exists(folder) and not os.path.isdir(folder):
            return False
    return True

# If we run python rig.py [command] [session], then this
# function ensures that the [session] exists
def get_argv_session_path():

    if len(sys.argv) == 2:
        print("You need to supply a session to run. The options are:")
        for dir in folders_list(SESSION_PATH):
            print(dir)
        exit(0)


    if sys.argv[2] not in folders_list(SESSION_PATH):
        print("Session " , sys.argv[2] , "not recognized. The option are:")
        for dir in folders_list(SESSION_PATH):
            print(dir)
        exit(0)

    return SESSION_PATH + sys.argv[2] + "/"


def load_session_yaml(filename):

    try:
        with open(filename, 'r') as f:
            yaml_data = yaml.safe_load(f)

    except IOError:
        print("Could not find: ", filename, ". Exiting")
        exit(1)

    return yaml_data


def link_module(module_src):

    # module_src = MODULE_PATH + filename + "/" + filename
    module_dst = RUN_PATH + os.path.basename(module_src)

    if not os.path.exists(module_src) and not os.path.isfile(module_src):
        print("Could not find ", module_src)
        exit(1)

    if os.path.islink(module_dst):
        print("[rig] Link exists: ", module_dst)
    else:
        print("[rig] Linking " + module_src)
        os.symlink("../" + module_src, module_dst)


#################################################
## Help message
#################################################

def display_help():
    print("----------------------------------------------")
    print("| Real-time rig booting system. Version ", VERSION, "|")
    print("----------------------------------------------")
    print("\n")
    print("Recognized commands:")
    print()
    print("initialize [session] -- initialize modules to be run in the session")
    print("run                  -- execute the booter module to start the experiment")

#################################################
## Initialize session
#################################################

def initialize_session():

# Begin by checking to see if the run folder exists.
# If the folder exists, abort. This is a safety measure
# to make sure we're not accidentally deleting something useful

    if not os.path.isdir(RUN_PATH):
        print("[rig] Creating run/ folder")
        os.makedirs(RUN_PATH)
    else:
        for (path, dirs, files) in os.walk(RUN_PATH):
            for file in files:
                if not os.path.islink(RUN_PATH + file):
                    print("The folder contains a file that is not a sym link. Remove this and try again.")
                    print(file)
                    exit(1)

# Begin by determining if we have been supplied a valid session

    session_folder = get_argv_session_path()
    print("[rig] Booting up: ", session_folder)


# Now go through the modules and link them appropriately

    yaml_data = load_session_yaml(session_folder + "session.yaml")

    for entry in yaml_data['modules']:
        for module in yaml_data['modules'][entry]:
            for link in module['links']:
                link_module(link)

    # for entry in yaml_data['modules']['start']:
    #     for link in entry['links']:
    #         link_module(link)


#################################################
## Run session
#################################################

def run_session():


    print("RUN")


#################################################
## Main
#################################################

if __name__ == '__main__':

# Do we look like we're in a rig structure where expect certain things?
# If not, exit immediately because something is terribly wrong

    if not is_correct_rig_folder_structure():
        print("This doesn't look like a rig folder structure. Exiting.")
        exit(0)

# If you run rig without parameters, return a display of the possible options

    if len(sys.argv) == 1:
        display_help()
        exit(0)

    if sys.argv[1] == 'initialize':
        initialize_session()

    if sys.argv[1] == 'run':
        run_session()
