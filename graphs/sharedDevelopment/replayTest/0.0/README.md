# Streams
```yaml
cursorData: # from behaviorFSM
	X: 4 bytes
	Y: 4 bytes
	state: [off/on] # 4 bytes
continuousNeural:  # from cerebusAdapter
	timestamps: 120 bytes
	BRANDS_time: 480 bytes
	udp_recv_time: 480 bytes
	samples: 5760 bytes
thresholdCrossings:  # from thresholdExtraction
	crossings: 192 bytes
	timestamps: 4 bytes
rawEMG:  # from cerebusAdapter
	timestamps: 40 bytes
	BRANDS_time: 160 bytes
	udp_recv_time: 160 bytes
	samples: 240 bytes
state:
	state: [start_trial, movement, reward, failure, between_trials] # 11 bytes
	time: 17 bytes
filteredCerebusAdapter:  # from thresholdExtraction
	timestamps: 120 bytes
	samples: 5760 bytes
taskInput:
	timestamps: 4 bytes
	BRANDS_time: 16 bytes
	udp_recv_time: 16 bytes
	samples: 6 bytes
behaviorControl:
	touch_active: 1 bytes
	reward: 1 bytes
thresholdValues:
	thresholds: 192 bytes
targetData:
	X: 4 bytes
	Y: 4 bytes
	width: 4 bytes
	height: 4 bytes
	state: [off/on/over] # 4 bytes
```