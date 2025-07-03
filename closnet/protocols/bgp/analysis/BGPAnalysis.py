# Core libraries
import re
import logging
import os
import json
from datetime import datetime

# Custom libraries
from closnet.experiment.ExperimentAnalysis import ExperimentAnalysis


class BGPAnalysis(ExperimentAnalysis):
    # IP addressing log file and information
    ADDRESSING_LOG_FILE = "addressing.log"
    PEER_IP_KEY = "peer_ip"
    
    # Timestamp information (Example timestamp in this format: 2024/04/30 04:09:33.947)
    TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M:%S.%f"
    TIMESTAMP_LENGTH = 23

    # Patterns to match in log file records
    INTF_FAILURE_PATTERN = re.compile(r"ZEBRA_INTERFACE_DOWN\s+(\S+)\s+vrf")
    INTF_ESTABLISHED_PATTERN = re.compile(
        r'%ADJCHANGE:\s+neighbor\s+'
        r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3})'   # peer IPv4 address
        r'.*?\bUp\b',                        # line must contain the word “Up”
        re.I                                 # case-insensitive
    )
    INTF_DISABLE_KEEPALIVE_PATTERN = re.compile(
        r'%NOTIFICATION'                  # constant prefix
        r'(?:\([^)]*\))?:\s+'             # optional "(Hard Reset)" or similar tag
        r'(?:sent|received)\s+'           # we ignore but must consume it
        r'(?:to|from)\s+neighbor\s+'      
        r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3})'# capture the peer IPv4 address
        r'\s+\d+/\d+\s+'                  # code/sub-code (4/0 or 6/10 ...)
        r'\('                             # opening parenthesis
            r'(?:Hold\s+Timer\s+Expired'  # 4/0 reason
            r'|Cease\/BFD\s+Down)'        # 6/10 reason
        r'\)',                            # closing parenthesis
        re.I
    )
    RECV_UPDATE_PATTERN = re.compile(r'rcvd\s+UPDATE.*wlen\s+(\d+)\s+attrlen\s+(\d+)\s+alen\s+(\d+)')

    # Message header sizes
    '''
    BGP UPDATE message structure
    19 bytes for the base BGP header
    4 bytes for the withdraw length and path attribute length
    +----------+ +--------+ +-------+ +---------------+ +--------------+  
    |  ETH II  | |  IPV4  | |  TCP  | |  BGP MESSAGE  | |  BGP UPDATE  | 
    +----------+ +--------+ +-------+ +---------------+ +--------------+ 
    '''
    ETH_II_HEADER_LEN = 14
    IPV4_HEADER_LEN = 20
    TCP_HEADER_LEN = 20
    BGP_HEADER_LEN = 23 # 19 bytes for the base header, 4 bytes for the two length fields in the UPDATE message.


    def __init__(self, experimentDirPath, **kwargs):
        super().__init__(experimentDirPath, **kwargs)

        # Update the timestamp to the FRR logging format     
        self.timestamp_format = self.TIMESTAMP_FORMAT

        # BGP peering data structures to confirm legitimacy of BFD failure events
        self.peers_seen = set()
        self.peer_state = {}
        self.startedExperiment = False

        # Read from the addressing file to import into a dict (if it is a soft link failure)
        if(self.experiment_type == self.SOFT_LINK_FAILURE):
            addressingFilePath = os.path.join(experimentDirPath, self.ADDRESSING_LOG_FILE)

            with open(addressingFilePath, "r") as addressingFile:
                self.addressing = json.load(addressingFile)


    def getEpochTime(self, timestamp, nodeName):
        '''
        Return a EPOCH timestamp based on the original timestamp.
        '''

        # If the log record doesn't have a timestamp, it cannot be analyzed and the log file is invalid.
        if self.timestamp_format is None:
            raise Exception("No timestamp format set, cannot convert to epoch time format")

        # Attempt to convert the standard timestamp into an EPOCH/POSIX timestamp.
        try:
            datetimeFormat = datetime.strptime(timestamp, self.timestamp_format)
        
            return int(datetime.timestamp(datetimeFormat) * 1000) # Reduce precision by moving milliseconds into main timestamp.

        # If there is no fractional part, pad with zeros and try again.
        except:
            logging.debug(f"[{nodeName}] Invalid log timestamp: {timestamp}, attempting to pad")
            timestamp_fixed = timestamp[:19] + '.000'
            return int(datetime.strptime(timestamp_fixed, self.timestamp_format).timestamp() * 1000)


    def localIntfForHoldTimerExparation(self, peerIP):
        '''
        Determine the interface name that is sending a message to a given BGP peer IPv4 address.
        '''
        
        # Grab the information from the log that describes the IP address on the other end of the link (the remote address).
        remoteIPDict = self.addressing.get(peerIP)

        # If that address isn't found, nothing more to do.
        if not remoteIPDict:
            return None, None

        # Grab the IP address from the local interface through the remote IP address.
        localIP = remoteIPDict[self.PEER_IP_KEY]
        localIPDict = self.addressing.get(localIP)

        # Return the node name (as a sanity check on the addressing dict) and the interface name
        return (localIPDict["node"] if localIPDict else None, localIPDict["intf"] if localIPDict else None)


    def parseLogFile(self, nodeName, logFile):
        '''
        Parse the records from the given node's log file to determine how it reacted to the experiment. 
        Results for the metrics specified are returned.
        '''
     
        convergenceTime = 0
        overhead = 0
        updated = False # Used for blast radius calculation. Nodes that are not updated are not part of the blast radius.

        with open(logFile) as file:
            # Iterate over every record in the node's log file
            for line in file:
                # Convert the record's timestamp into EPOCH formatting
                recordTimestamp = self.getEpochTime(line[:self.TIMESTAMP_LENGTH], nodeName)

                # Determine where this timestamp fits into the experiment timeframe
                recordIsWithinExperimentTimeframe = self.isValidLogRecord(recordTimestamp, useExperimentStartTime=True)

                # When the first record after the experiment start time is found, make sure the node's interfaces are BGP-ready.
                if(not self.startedExperiment and recordIsWithinExperimentTimeframe):
                    self.startedExperiment = True # We're within the experiment timeframe, no need to check for it anymore.

                    # If the node does not have all BGP peers in the established state by this point, the experiment failed. 
                    ready = self.peers_seen and all(self.peer_state.get(ip) for ip in self.peers_seen)
                    if(not ready):
                        earlyFailureMessage = f"[{nodeName}] One or more interfaces were not ready before the start time {self.start_time}!"
                        logging.debug(earlyFailureMessage)
                        raise Exception(earlyFailureMessage)

                ###### INTERFACE MOVED TO ESTABLISHED STATE IN BGP LOG ######
                if(match := self.INTF_ESTABLISHED_PATTERN.search(line)):
                    peerIP = match.group('ip')
                    self.peers_seen.add(peerIP)
                    self.peer_state[peerIP] = True   

                ###### INTERFACE FAILED (HARD LINK FAILURE) LOG ######
                elif(match := self.INTF_FAILURE_PATTERN.search(line)):
                    # Grab failed interface's name.
                    intfName = match.group(1)

                    # If the failure occurred after the end of the experiment, it's part of the experiment teardown and it is ignored.
                    if recordTimestamp > self.stop_time:
                        continue

                    logging.debug(f"[{nodeName}] Failed interface detected: {line.strip()}")
                    logging.debug(f"[{nodeName}] Failed interface timestamp: {recordTimestamp}")
                    logging.debug(f"[{nodeName}] Failed interface name: {intfName}")

                    # If the failure occurred prior to the start of the experiment, it was a failed experiment.
                    if recordTimestamp < self.start_time:
                        earlyFailureMessage = f"[{nodeName}] Interface failure at {recordTimestamp} is earlier than experiment start at {self.start_time}!"
                        logging.debug(earlyFailureMessage)
                        raise Exception(earlyFailureMessage)

                    # Analyze the failure
                    result, convergenceTime = self.parseIntfFailure(nodeName, recordTimestamp, intfName, convergenceTime, self.FAILED_LOG)
                    updated = True # The node's state has been updated as a result of a failure.

                    # As long as the failure is either interface on the designated failed link, it's valid. Otherwise, the experiment failed.
                    if(result == self.VALID_INTERFACE_FAILURE):
                        logging.debug(f"[{nodeName}] Successfully determined to be failed node.")

                    elif(result == self.VALID_NEIGHBOR_FAILURE):
                        logging.debug(f"[{nodeName}] Successfully determined to be failed neighbor node.")

                    elif(result == self.INVALID_INTERFACE_FAILURE):
                        invalidFailureMessage = f"[{nodeName}] Interface failure at {recordTimestamp} is invalid!"
                        logging.debug(invalidFailureMessage)
                        raise Exception(invalidFailureMessage)

                ###### INTERFACE DISABLED IN BGP (SOFT LINK FAILURE) LOG ######
                elif(match := self.INTF_DISABLE_KEEPALIVE_PATTERN.search(line)):
                    # Grab the IPv4 address the message was sent to.
                    peerIP = match.group('ip')  # example: '172.16.16.2'

                    # Note the interface as disabled for pre-experiment confirmation that all interfaces are up and ready
                    self.peers_seen.add(peerIP) 
                    self.peer_state[peerIP] = False

                    # If the failure occurred before or after the experiment, it doesn't matter. Pre-failures are checked at experiment start.
                    if(not recordIsWithinExperimentTimeframe):
                        continue

                    # Grab the interface name that sent or received the message from the IP address
                    recordNodeName, intfName = self.localIntfForHoldTimerExparation(peerIP)

                    logging.debug(f"[{nodeName}] Disabled interface detected: {line.strip()}")
                    logging.debug(f"[{nodeName}] Disabled interface timestamp: {recordTimestamp}")
                    logging.debug(f"[{nodeName}] Disabled interface name: {intfName}")

                    # Analyze the failure
                    result, convergenceTime = self.parseIntfFailure(recordNodeName, recordTimestamp, intfName, convergenceTime, self.DISABLED_LOG)
                    updated = True # The node's state has been updated as a result of a failure.

                    # As long as the failure is either interface on the designated failed link, it's valid. Otherwise, the experiment failed.
                    if(result == self.VALID_INTERFACE_FAILURE):
                        logging.debug(f"[{nodeName}] Successfully determined to be disabled node.")

                    elif(result == self.VALID_NEIGHBOR_FAILURE):
                        logging.debug(f"[{nodeName}] Successfully determined to be disabled neighbor node.")

                    elif(result == self.INVALID_INTERFACE_FAILURE):
                        invalidFailureMessage = f"[{nodeName}] Interface disabled at {recordTimestamp} is invalid!"
                        logging.debug(invalidFailureMessage)
                        raise Exception(invalidFailureMessage) 

                ###### BGP UPDATE MESSAGE LOG ######
                elif(self.failureDetected() and 
                     self.isValidLogRecord(recordTimestamp) and
                      (match := self.RECV_UPDATE_PATTERN.search(line))):
                    
                    # Parse the message's withdraw length (wlen), attribute length (attrlen), and NLRI length (alen).
                    wlen, attrlen, alen = map(int, match.groups())

                    # If any of those three values are > 0, then the message describes a valid UPDATE.
                    if(any(val > 0 for val in (wlen, attrlen, alen))):
                        convergenceTime = max(convergenceTime, recordTimestamp)
                        updated = True
                        bgp_update_len = wlen + attrlen + alen

                        # The overhead is the fixed header sizes plus the size of the BGP UPDATE message found when parsing it.
                        overhead += (
                            self.ETH_II_HEADER_LEN + # Ethernet-II header
                            self.IPV4_HEADER_LEN +   # IPv4 header
                            self.TCP_HEADER_LEN +    # TCP header
                            self.BGP_HEADER_LEN +    # BGP base header 
                            bgp_update_len           # BGP UPDATE 
                        )
                        
                        logging.debug(f"[{nodeName}] BGP UPDATE detected: {line.rstrip()}")
                        logging.debug(f"[{nodeName}] UPDATE timestamp: {recordTimestamp}")

        logging.debug(f"[{nodeName}] Final values: Convergence Time = {convergenceTime} | Updated = {updated} | Overhead = {overhead}")

        return convergenceTime, updated, overhead
