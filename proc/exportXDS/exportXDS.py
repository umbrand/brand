#! /usr/bin/env python
# -*- coding: utf-8 -*-
# exportXDS.py


"""
exportXDS.py

takes data from a dump.rdb snapshot file and exports it as an XDS so that it can be
analyzed in python and matlab using currently existing scripts

Going to start by exporting .mat files using scipy, then will try shifting to .hdf5
to allow for larger files


@author Kevin Human Primate
"""

import h5py, scipy
from redis import Redis
import numpy as np
from struct import pack,unpack



'''######################################################
###    initialize all support functions
######################################################'''
def initialize_xds():
    # start with initalizing the easy fields
    xds = {
            u'bin_width'            :   0,
            u'time_frame'           :   None,
            u'has_EMG'              :   0,
            u'has_force'            :   0,
            u'has_kin'              :   0,
            u'sorted'               :   0,
            u'unit_names'           :   None, # this will need to be dealt with later...
            u'spikes'               :   None, # same
            u'EMG'                  :   None, # same
            u'EMG_names'            :   None,
            u'raw_EMG'              :   None,
            u'raw_EMG_time_frame'   :   None,
            u'force'                :   None,
            u'kin_p'                :   None,
            u'kin_v'                :   None,
            u'kin_a'                :   None,
            u'trial_info_table_header': None,
            u'trial_info_table'     :   None,
            u'trial_gocue_time'     :   None,
            u'trial_start_time'     :   None,
            u'trial_end_time'       :   None,
            u'trial_result'         :   None,
            u'trial_target_dir'     :   None,
            u'trial_target_corners' :   None}
    
    
    # then add the meta sub-dictionary
    xds[u'meta'] = {
            u'cdsVersion'       :   None, # not applicable -- not converting from CDS
            u'processedTime'    :   '',
            u'rawFileName'      :   '',
            u'dataSource'       :   'RANDS',
            u'ranBy'            :   '',
            u'knownProblems'    :   '',
            u'dateTime'         :   '',
            u'task'             :   '',
            u'lab'              :   None,
            u'monkey'           :   '',
            u'hasEMG'           :   0,
            u'hasLfp'           :   0,
            u'hasKinematics'    :   0,
            u'hasForce'         :   0,
            u'hasAnalog'        :   0,
            u'hasUnits'         :   0,
            u'hasTriggers'      :   0,
            u'hasBumps'         :   0,
            u'hasChaoticLoad'   :   0,
            u'array'            :   '',
            u'numSorted'        :   0,
            u'hasSorting'       :   0,
            u'numWellSorted'    :   0,
            u'numDualUnits'     :   0,
            u'percentStill'     :   0,
            u'stillTime'        :   0,
            u'numTrials'        :   0,
            u'numReward'        :   0,
            u'numAbort'         :   0,
            u'numFail'          :   0,
            u'numIncomplete'    :   0,
            u'aliasList'        :   '',
            u'cdsName'          :   None, # not applicable -- not converting through CDS
            u'dataWindow'       :   (0,0),
            u'duration'         :   0}

    return xds




'''######################################################
###    initialize the xds dict (python)
######################################################'''
xds = initialize_xds()






 
'''######################################################
###     bring in threshold crossings
######################################################'''













'''######################################################
###     task data
######################################################'''















'''######################################################
###     EMG data
######################################################'''















'''######################################################
###     make sure everything's aligned in time
######################################################'''











'''######################################################
###     write to .mat file
######################################################'''








