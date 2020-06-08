function cerebusData = parseBroadbandFromCerebus(n, numPackets, data, length, modelConstants)
%#codegen 

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% parse cerebus broadband with common average referencing
%
% Vikash
% Stanford NPTL
% 2/2012
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Generic cbPKT data format
%
% values are little endian
%
% uint32 time  // cerebus 30kHz clock
% uint16 chid  // channel id (must be < 0x8000)
% uint8  type
% uint8  dlen  // number of 32-bit (4 byte) data chunks that follows
% *****  data
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% cbPKT spike data format
%
% header info: 20 bytes
% spike waveform, max of 128 points (256 bytes)
% internal lab convention of 48 points (96 bytes) results in 1.2 ms data snippet
%
% uint32 time        // cerebus 30kHz clock
% uint16 chid        // channel id (must be 0 < chid < 145)
% uint8  unit        // unit classification (1-5 = sorted unit num, 0 = unclassified, 31 = artifact, 30 = background)
% uint8  dlen        // length of 32-bit (4 byte) data chunks that follows (fixed to 27 for our lab)
% float  fPattern[2] // used for automatic spike sorting
% int16  nPeak       // highest value in spike
% int16  nValley     // lowest values in spike
% int16  wave[48]    // spike waveform
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%



% constants
numCerebusChannels = modelConstants.cerebus.numCerebusChannels;
cerebusIpSource = modelConstants.cerebus.cerebusIpSource;
cerebusIpDest = modelConstants.cerebus.cerebusIpDest;
maxSamplesInMS = modelConstants.cerebus.maxSamplesInMS;

IP_UDP_HEADER_SIZE = uint16(28); % IP header = 20, UDP header = 8

cbPKT_sample_dlen = uint8(numCerebusChannels/2);   

% static variables
% these will contain the final output variables at the end of the for iterator
persistent samplesP;
persistent sampleTimesP; % The uint32 timestamp in the generic header
persistent numSamplesP;

persistent droppedUDPPacketsP; % How many UDP packets have been dropped since we started running this program
persistent lastUDPPacketNumberP; % What is the 

persistent firstCerebusTimeP;
persistent lastCerebusTimeP;

% init persistents
if isempty(droppedUDPPacketsP)
    samplesP = int16(zeros(maxSamplesInMS, numCerebusChannels));
    sampleTimesP = uint32(zeros(maxSamplesInMS,1));
    numSamplesP = uint32(0);
    
    droppedUDPPacketsP = uint32(0);
    lastUDPPacketNumberP = int32(-1);
    
    firstCerebusTimeP = uint32(0);
    lastCerebusTimeP = uint32(0);
end


if n == 1
    samplesP = int16(zeros(maxSamplesInMS, numCerebusChannels));
    numSamplesP = uint32(0);
    sampleTimesP =uint32(zeros(maxSamplesInMS, 1));
end

% Only process packet if it is from cerebus
if(all(data(13:16) == cerebusIpSource') ...
        && all(data(17:20) == cerebusIpDest'))
    
    % yank current packet num in IP header
    udpPacketNumber = int32(data(5))*int32(256) + int32(data(6));
    
    % check for dropped packet
    if(lastUDPPacketNumberP ~= -1)
        droppedUDPPacketsP = droppedUDPPacketsP + uint32(mod(udpPacketNumber-lastUDPPacketNumberP, 2^16) - 1);
    end
    
    lastUDPPacketNumberP = udpPacketNumber;
    
    cbPKT_startpos = uint16(IP_UDP_HEADER_SIZE+1);
    
    firstCbPkt = true;
        
    % parse and copy each spike cbPKT
    while cbPKT_startpos < length
        
        cbPKT_chid_lsb = data(cbPKT_startpos + 4);  % extract channel lsb
        cbPKT_chid_msb = data(cbPKT_startpos + 5);  % extract channel msb
        cbPKT_type = data(cbPKT_startpos + 6);      % extract unit classification
        cbPKT_dlen = data(cbPKT_startpos + 7);      % extract data length of "non header" data
        
        if( (n== 1) && (firstCbPkt) )
            firstCerebusTimeP = uint32(data(cbPKT_startpos))*2^(0*8) + uint32(data(cbPKT_startpos+1))*2^(1*8) + uint32(data(cbPKT_startpos+2))*2^(2*8) + uint32(data(cbPKT_startpos+3))*2^(3*8);
            firstCbPkt = false;
        end
        
        lastCerebusTimeP = uint32(data(cbPKT_startpos))*2^(0*8) + uint32(data(cbPKT_startpos+1))*2^(1*8) + uint32(data(cbPKT_startpos+2))*2^(2*8) + uint32(data(cbPKT_startpos+3))*2^(3*8);
        
        
        % Check for group packet type 5 (broadband, 30 kS/s)    
        if (cbPKT_chid_lsb == 0) && (cbPKT_chid_msb == 0) && ...
                (cbPKT_dlen == cbPKT_sample_dlen) && ...
                (cbPKT_type == 5)
            
            numSamplesP = numSamplesP + 1;
            
            % This looks really complicated because we have to unpack
            % data() byte by byte and then reconstruct what the sampleTImes
            sampleTimesP(numSamplesP) = uint32(data(cbPKT_startpos))*2^(0*8) + uint32(data(cbPKT_startpos+1))*2^(1*8) + uint32(data(cbPKT_startpos+2))*2^(2*8) + uint32(data(cbPKT_startpos+3))*2^(3*8);
            
            for x = coder.unroll(1:numCerebusChannels)

                % tmpSample is just the data at one point
                tmpSample = int32(data(cbPKT_startpos + 8 + 2*x - 2))*(2^(0*8)) + int32(data(cbPKT_startpos + 8 + 2*x - 1))*(2^(1*8));

                % Edge case dealing with uint32 vs int32
                if(tmpSample > 2^15)
                    samplesP(numSamplesP, x) = int16(tmpSample - 2^16);
                else
                    samplesP(numSamplesP, x) = int16(tmpSample);
                end
                
            end
            % Common average reference:
            samplesP(numSamplesP, :) = samplesP(numSamplesP, :) - mean(samplesP(numSamplesP, :)); 
        end
        
        cbPKT_startpos = cbPKT_startpos + uint16(8) + uint16(cbPKT_dlen)*4;
    end
    
    
end

cerebusData.droppsedUDPPackets = droppedUDPPacketsP;
cerebusData.lastUDPPacketNumber = lastUDPPacketNumberP;

% update large arrays only at end of for loop
if n == numPackets
    cerebusData.numSamples = numSamplesP;
    cerebusData.samples = samplesP;
    cerebusData.sampleTimes = sampleTimesP;
    
    cerebusData.firstCerebusTime = firstCerebusTimeP;
    cerebusData.lastCerebusTime = lastCerebusTimeP;
else
    cerebusData.numSamples = uint32(0);
    cerebusData.samples = coder.nullcopy(int16(zeros(maxSamplesInMS, numCerebusChannels)));
    cerebusData.sampleTimes = coder.nullcopy(uint32(zeros(maxSamplesInMS,1)));
    
    cerebusData.firstCerebusTime = uint32(0);
    cerebusData.lastCerebusTime = uint32(0);
end
