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
    RECV_UPDATE_PATTERN = re.compile(r'rcvd\s+UPDATE.*wlen\s+(\d+)\s+attrlen\s+(\d+)\s+alen\s+(\d+)')
    INTF_DISABLE_KEEPALIVE_PATTERN = re.compile(
    r'%NOTIFICATION:\s+'
    r'(?P<dir>sent|received)\s+'           # sent | received
    r'(?:to|from)\s+neighbor\s+'
    r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+'  # peer IPv4
    r'\d+/\d+\s+'                          # code/sub-code (e.g. 4/0)
    r'\(Hold\s+Timer\s+Expired\)',         # *only* this reason
    re.I
)

    # Message header sizes
    '''
    BGP UPDATE message structure
    19 bytes for the general BGP header
    4 bytes for the withdraw length and path attribute length
    +----------+ +--------+ +-------+ +---------------+ +--------------+  
    |  ETH II  | |  IPV4  | |  TCP  | |  BGP MESSAGE  | |  BGP UPDATE  | 
    +----------+ +--------+ +-------+ +---------------+ +--------------+ 
    '''
    ETH_II_HEADER_LEN = 14
    IPV4_HEADER_LEN = 20
    TCP_HEADER_LEN = 20
    BGP_HEADER_LEN = 23 


    def __init__(self, experimentDirPath, **kwargs):
        super().__init__(experimentDirPath, **kwargs)

        # Update the timestamp to the FRR logging format     
        self.timestamp_format = self.TIMESTAMP_FORMAT

        # Read from the addressing file to import into a dict (if it is a soft link failure)
        if(self.experiment_type == self.SOFT_LINK_FAILURE):
            addressingFilePath = os.path.join(experimentDirPath, self.ADDRESSING_LOG_FILE)
            with open(addressingFilePath, "r") as addressingFile:
                self.addressing = json.load(addressingFile)


    def getEpochTime(self, timestamp, nodeName):
        '''
        Return a epoch timestamp based on the original timestamp.
        '''

        if self.timestamp_format is None:
            raise Exception("No timestamp format set, cannot convert to epoch time format")

        try:
            datetimeFormat = datetime.strptime(timestamp, self.timestamp_format)
        
            return int(datetime.timestamp(datetimeFormat) * 1000) # Reduce precision by moving milliseconds into main timestamp.

        # No fractional part - pad with zeros and try again
        except:
            logging.debug(f"[{nodeName}] Invalid log timestamp: {timestamp}, attempting to pad")
            timestamp_fixed = timestamp[:19] + '.000'
            return int(datetime.strptime(timestamp_fixed, self.timestamp_format).timestamp() * 1000)


    def localIntfForHoldTimerExparation(self, peerIP):
        # Grab the information from the log that describes the IP address on the other end of the link (the remote address) 
        remoteIPDict = self.addressing.get(peerIP)

        # If that address isn't found, nothing more to do.
        if not remoteIPDict:
            return None, None

        # Grab the IP address from the local interface through the remote IP address
        localIP = remoteIPDict[self.PEER_IP_KEY]
        localIPDict = self.addressing.get(localIP)

        return (localIPDict["node"] if localIPDict else None, localIPDict["intf"] if localIPDict else None)


    def parseLogFile(self, nodeName, logFile):    
        convergenceTime = 0
        overhead = 0
        updated = False # Used for blast radius calculation. Nodes that are not updated are not part of the blast radius.

        with open(logFile) as file:
            # Iterate over every record in the node's log file
            for line in file:
                # Convert the timestamp into Epoch formatting
                recordTimestamp = self.getEpochTime(line[:self.TIMESTAMP_LENGTH], nodeName)

                # Check to see if the log record describes an interface failure
                interfaceFailure = self.INTF_FAILURE_PATTERN.search(line)
                if interfaceFailure:
                    # Grab failed interface's name and the timestamp of the log record
                    intfName = interfaceFailure.group(1)

                    # If the failure occurred after the end of the experiment, it doesn't matter (and is common when tearing down the topology)
                    if recordTimestamp > self.stop_time:
                        continue

                    logging.debug(f"[{nodeName}] Failed interface detected: {line}")
                    logging.debug(f"[{nodeName}] Failed interface timestamp: {recordTimestamp}")
                    logging.debug(f"[{nodeName}] Failed interface name: {intfName}")

                    # If the failure occurred prior to the start of the experiment, it was a failed experiment
                    if recordTimestamp < self.start_time:
                        earlyFailureMessage = f"[{nodeName}] Interface failure at {recordTimestamp} is earlier than experiment start at {self.start_time}!"
                        logging.debug(earlyFailureMessage)
                        raise Exception(earlyFailureMessage)

                    # Analyze the failure
                    result, convergenceTime = self.parseIntfFailure(nodeName, recordTimestamp, intfName, convergenceTime, self.FAILED_LOG)
                    updated = True # The node's state has been updated as a result of a failure.

                    if(result == self.VALID_INTERFACE_FAILURE):
                        logging.debug(f"[{nodeName}] Successfully determined to be failed node.")

                    elif(result == self.VALID_NEIGHBOR_FAILURE):
                        logging.debug(f"[{nodeName}] Successfully determined to be failed neighbor node.")

                    elif(result == self.INVALID_INTERFACE_FAILURE):
                        invalidFailureMessage = f"[{nodeName}] Interface failure at {recordTimestamp} is invalid!"
                        logging.debug(invalidFailureMessage)
                        raise Exception(invalidFailureMessage)

                # Check to see if the log record describes an interface failure
                interfaceDisabled = self.INTF_DISABLE_KEEPALIVE_PATTERN.search(line)
                if interfaceDisabled:
                    # Grab the direction of failure message and the IPv4 address it was sent to.
                    direction = interfaceDisabled.group('dir') # 'sent' or 'received'
                    peerIP   = interfaceDisabled.group('ip')  # example: '172.16.16.2'

                    # If the failure occurred after the end of the test, it doesn't matter (and is common when tearing down the topology)
                    if recordTimestamp > self.stop_time:
                        continue

                    # Grab the interface name that sent or received the message from the IP address
                    recordNodeName, intfName = self.localIntfForHoldTimerExparation(peerIP)

                    logging.debug(f"[{nodeName}] Disabled interface detected: {line.strip()}")
                    logging.debug(f"[{nodeName}] Disabled interface timestamp: {recordTimestamp}")
                    logging.debug(f"[{nodeName}] Disabled interface name: {intfName}")

                    # If the failure occurred prior to the start of the experiment, it was a failed experiment
                    if recordTimestamp < self.start_time:
                        earlyFailureMessage = f"[{nodeName}] Interface disabled at {recordTimestamp} is earlier than experiment start at {self.start_time}!"
                        logging.debug(earlyFailureMessage)
                        raise Exception(earlyFailureMessage)

                    # Analyze the failure
                    result, convergenceTime = self.parseIntfFailure(recordNodeName, recordTimestamp, intfName, convergenceTime, self.DISABLED_LOG)
                    updated = True # The node's state has been updated as a result of a failure.

                    if(result == self.VALID_INTERFACE_FAILURE):
                        logging.debug(f"[{nodeName}] Successfully determined to be disabled node.")

                    elif(result == self.VALID_NEIGHBOR_FAILURE):
                        logging.debug(f"[{nodeName}] Successfully determined to be disabled neighbor node.")

                    elif(result == self.INVALID_INTERFACE_FAILURE):
                        invalidFailureMessage = f"[{nodeName}] Interface disabled at {recordTimestamp} is invalid!"
                        logging.debug(invalidFailureMessage)
                        raise Exception(invalidFailureMessage) 

                # For all other record types, ignore if its not within the experiment time frame.
                if(not self.isValidLogRecord(recordTimestamp, useExperimentStartTime=True)):
                    continue

                # If the node received updated prefix information via a BGP UPDATE message, parse the message
                receivedBGPUpdate = self.RECV_UPDATE_PATTERN.search(line)
                if receivedBGPUpdate:
                    #  Ignore the record if its not within the experiment time frame post-failure.
                    if not self.isValidLogRecord(recordTimestamp):
                        continue

                    wlen, attrlen, alen = map(int, receivedBGPUpdate.groups())

                    if(any(val > 0 for val in (wlen, attrlen, alen))):
                        convergenceTime = max(convergenceTime, recordTimestamp)
                        updated = True
                        overhead += wlen + attrlen + alen + self.ETH_II_HEADER_LEN + self.IPV4_HEADER_LEN + self.TCP_HEADER_LEN + self.BGP_HEADER_LEN

                        logging.debug(f"[{nodeName}] BGP UPDATE detected: {line.rstrip()}")
                        logging.debug(f"[{nodeName}] UPDATE timestamp: {recordTimestamp}")

        logging.debug(f"[{nodeName}] Final values: Convergence Time = {convergenceTime} | Updated = {updated} | Overhead = {overhead}")

        return convergenceTime, updated, overhead
