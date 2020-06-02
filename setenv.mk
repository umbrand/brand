ifeq ($(ROOT), )
$(error "ROOT is undefined")
endif

export HIREDIS_PATH=$(ROOT)/lib/hiredis
export LPCNET_PATH=$(ROOT)/lib/LPCNet
export LPCNET_LIB_PATH=$(ROOT)/lib/LPCNet/.libs

export BIN_PATH=$(ROOT)/bin
export GENERATED_PATH=$(BIN_PATH)/generated
$(shell mkdir -p $(GENERATED_PATH))
