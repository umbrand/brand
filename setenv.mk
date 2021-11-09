ifeq ($(ROOT), )
$(error "ROOT is undefined")
endif

export HIREDIS_PATH=$(ROOT)/lib/hiredis
export LPCNET_PATH=$(ROOT)/lib/LPCNet
export REDIS_PATH=$(ROOT)/lib/redis
export LPCNET_LIB_PATH=$(ROOT)/lib/LPCNet/.libs

# save all compiled nodes in local node folder
# so that we have consistency in where the run
# command will look for nodes
export BIN_PATH=$(ROOT)/bin
export GENERATED_PATH=$(BIN_PATH)/generated
$(shell mkdir -p $(GENERATED_PATH))
