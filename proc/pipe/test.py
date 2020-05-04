import sys
# insert at 1, 0 is the script path (or '' in REPL)
sys.path.insert(1, '../../lib/')

from redisTools import *

initializeRedisFromYAML()
