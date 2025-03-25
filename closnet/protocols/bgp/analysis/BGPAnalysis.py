# Core libraries
import re
import logging
from datetime import datetime

# Custom libraries
from closnet.experiment.ExperimentAnalysis import ExperimentAnalysis


class BGPAnalysis(ExperimentAnalysis):
    # Timestamp information (Example timestamp in this format: 2024/04/30 04:09:33.947)
    TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M:%S.%f"
    TIMESTAMP_LENGTH = 23

    # Patterns to match in log file records
    INTF_FAILURE_PATTERN = re.compile(r"ZEBRA_INTERFACE_DOWN\s+(\S+)\s+vrf")
    RECV_UPDATE_PATTERN = re.compile(r'rcvd\s+UPDATE.*wlen\s+(\d+)\s+attrlen\s+(\d+)\s+alen\s+(\d+)')

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


    def __init__(self, experimentDirPath):
        super().__init__(experimentDirPath)

        # Update the timestamp to the FRR logging format     
        self.timestamp_format = self.TIMESTAMP_FORMAT


    def getEpochTime(self, timestamp):
        '''
        Return a epoch timestamp based on the original timestamp.
        '''

        if self.timestamp_format is None:
            raise Exception("No timestamp format set, cannot convert to epoch time format")

        datetimeFormat = datetime.strptime(timestamp, self.timestamp_format)
        
        return int(datetime.timestamp(datetimeFormat) * 1000) # Reduce precision by moving milliseconds into main timestamp.
    

    def parseFailureLogRecord(self, nodeName, intfName, recordTimestamp) -> None:
        # If the interface failure log came from the neighbor of the node that lost an interface.
        if(self.isFailedNeighbor(nodeName)):
            if(self.isFailedNeighborInterface(intfName)):
                logging.debug(f"[{nodeName}] Successfully determined to be failed neighbor node.")
            else:
                raise Exception("Log error: Multiple failures on failed neighbor, Please check logs.")

        # If the interface failure log came from the node that lost an interface.
        elif(self.isFailedNode(nodeName)):
            if(self.isFailedInterface(intfName)):
                self.intf_failure_time = recordTimestamp

                logging.debug(f"[{nodeName}] Successfully determined to be failed node.")
            else:
                raise Exception("Log error: Multiple failures on failed node, Please check logs.")

        # If the interface failure log came from any other node, there was an issue with the experiment.
        else:
            raise Exception(f"Log error: Interface failure on node {nodeName}, Please check logs.")
        
        return
    

    def parseLogFile(self, nodeName, logFile):    
        convergenceTime = 0
        overhead = 0
        updated = False # Used for blast radius calculation. Nodes that are not updated are not part of the blast radius.

        with open(logFile) as file:
            # Iterate over every record in the node's log file
            for line in file:
                # Convert the timestamp into Epoch formatting
                recordTimestamp = self.getEpochTime(line[:self.TIMESTAMP_LENGTH])

                # Check to see if the log record describes an interface failure
                interfaceFailure = self.INTF_FAILURE_PATTERN.search(line)
                if interfaceFailure:
                    # If the failure occurred prior to the start of the test, it was a failed test
                    if recordTimestamp < self.start_time:
                        raise Exception(f"[{nodeName}] Interface failure at {recordTimestamp} is earlier than experiment start at {self.start_time}!")

                    # If the failure occurred after the end of the test, it doesn't matter (and is common when tearing down the topology)
                    if recordTimestamp > self.stop_time:
                        continue

                    # Grab failed interface's name
                    intfName = interfaceFailure.group(1)

                    logging.debug(f"[{nodeName}] Failed interface detected: {line.rstrip()}")
                    logging.debug(f"[{nodeName}] Failed interface timestamp: {recordTimestamp}")
                    logging.debug(f"[{nodeName}] Failed interface name: {intfName}")

                    # The only valid failures within the experiment time frame are the specified node and its neighbor
                    self.parseFailureLogRecord(nodeName, intfName, recordTimestamp)
                    convergenceTime = max(convergenceTime, recordTimestamp)
                    updated = True

                # For all other record types, ignore if its not within the experiment time frame.
                if(not self.isValidLogRecord(recordTimestamp, useExperimentStartTime=True)):
                    continue

                # If the node received updated prefix information via a BGP UPDATE message, parse the message
                receivedBGPUpdate = self.RECV_UPDATE_PATTERN.search(line)
                if receivedBGPUpdate:
                    wlen, attrlen, alen = map(int, receivedBGPUpdate.groups())

                    if(any(val > 0 for val in (wlen, attrlen, alen))):
                        convergenceTime = max(convergenceTime, recordTimestamp)
                        updated = True
                        overhead += wlen + attrlen + alen + self.ETH_II_HEADER_LEN + self.IPV4_HEADER_LEN + self.TCP_HEADER_LEN + self.BGP_HEADER_LEN

                        logging.debug(f"[{nodeName}] BGP UPDATE detected: {line.rstrip()}")
                        logging.debug(f"[{nodeName}] UPDATE timestamp: {recordTimestamp}")

        logging.debug(f"[{nodeName}] Final values: Convergence Time = {convergenceTime} | Updated = {updated} | Overhead = {overhead}")

        return convergenceTime, updated, overhead
