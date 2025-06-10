# Core libraries
import re
import logging

# Custom libraries
from closnet.experiment.ExperimentAnalysis import ExperimentAnalysis

class MTPAnalysis(ExperimentAnalysis):
    """
    MTPAnalysis is analogous to BGPAnalysis, but adapted to parse MTP logs.
    We look for:

    1) An interface failure line on the failing node:
       "Detected a failure, shut down port L_1-eth1 at time 1742490729154"

    2) A failure update line on other nodes:
       "FAILURE UPDATE message received at 1742490729396, on port L_3-eth1"
       followed (possibly on next line) by:
       "Message size = 20"

    3) A neighbor's keep-alive line:
       "--------Disabled for port T_1-eth1 due to a missing KEEP ALIVE at time 1742490729396--------"

    Many lines don't contain timestamps at all; we ignore those.
    """

    # Patterns to match in log file records
    INTF_FAILURE_PATTERN = re.compile(r'Detected a failure, shut down port ([^ ]+) at time (\d{13})')
    INTF_DISABLE_KEEPALIVE_PATTERN = re.compile(r'Disabled for port ([^ ]+) due to a missing KEEP ALIVE at time (\d{13})')
    RECV_UPDATE_PATTERN = re.compile(r'FAILURE UPDATE message received at (\d{13}), on port ([^ ]+)')
    RECV_UPDATE_SIZE_PATTERN = re.compile(r'Message size\s*=\s*(\d+)')


    def __init__(self, experimentDirPath):
        super().__init__(experimentDirPath)
        # MTP lines show the timestamp in the text itself, e.g., "... at time 1742490729154" so no self.timestamp_format needed.


    def parseLogFile(self, nodeName, logFile):
        convergenceTime = 0
        overhead = 0
        updated = False # Used for blast radius calculation. Nodes that are not updated are not part of the blast radius.

        # If a valid MTP Update message is parsed, the next line must be read because it is the message size.
        lastUpdateValid = False

        with open(logFile) as file:
            # Iterate over every record in the node's log file
            for line in file:
                # Strip out additional whitespace and such
                line = line.strip()

                # Check to see if the log record describes an interface failure
                interfaceFailure = self.INTF_FAILURE_PATTERN.search(line)
                if interfaceFailure:
                    # Grab failed interface's name and the timestamp of the log record
                    intfName = interfaceFailure.group(1)
                    recordTimestamp = int(interfaceFailure.group(2))

                    # If the failure occurred prior to the start of the experiment, it was a failed experiment
                    if recordTimestamp < self.start_time:
                        raise Exception(f"[{nodeName}] Interface failure at {recordTimestamp} is earlier than experiment start at {self.start_time}!")

                    # If the failure occurred after the end of the experiment, it doesn't matter (and is common when tearing down the topology)
                    if recordTimestamp > self.stop_time:
                        continue

                    # Analyze the failure
                    convergenceTime = self.parseIntfFailure(nodeName, line, recordTimestamp, intfName, convergenceTime)
                    updated = True

                    # move onto the next record
                    lastUpdateValid = False
                    continue

                # If the node received updated VID information via an MTP Update, parse the message.
                receivedMTPUpdate = self.RECV_UPDATE_PATTERN.search(line)
                if receivedMTPUpdate:
                    recordTimestamp = int(receivedMTPUpdate.group(1))

                    #  Ignore the record if its not within the experiment time frame.
                    if not self.isValidLogRecord(recordTimestamp):
                        lastUpdateValid = False
                        continue

                    # Use the timestamp to update metric values, as it is a legit MTP update
                    convergenceTime = max(convergenceTime, recordTimestamp)
                    updated = True

                    logging.debug(f"[{nodeName}] MTP Update detected: {line}")


                    # Now we allow exactly one subsequent “Message size” line
                    lastUpdateValid = True
                    continue

                # Check to see if the log record describes an interface that was disabled due to missing keep-alive messages
                interfaceDisabled = self.INTF_DISABLE_KEEPALIVE_PATTERN.search(line)
                if interfaceDisabled:
                    intfName  = interfaceDisabled.group(1)
                    recordTimestamp  = int(interfaceDisabled.group(2))

                    # If the failure occurred prior to the start of the test, it was a failed test
                    if recordTimestamp < self.start_time:
                        raise Exception(f"[{nodeName}] Interface disabled at {recordTimestamp} is earlier than experiment start at {self.start_time}!")

                    # If the failure occurred after the end of the test, it doesn't matter (and is common when tearing down the topology)
                    if recordTimestamp > self.stop_time:
                        lastUpdateValid = False
                        continue

                    # Analyze the interface timeout
                    convergenceTime = self.parseIntfTimeout(nodeName, line, recordTimestamp, intfName, convergenceTime)
                    updated = True

                    # move onto the next record
                    lastUpdateValid = False
                    continue

                # For MTP updates received, parse the size of the message.
                receivedMTPUpdateSize = self.RECV_UPDATE_SIZE_PATTERN.search(line)
                if receivedMTPUpdateSize and lastUpdateValid:
                    updateSize = int(receivedMTPUpdateSize.group(1))
                    overhead += updateSize
                    lastUpdateValid = False
                    
                    logging.debug(f"[{nodeName}] Message size: {updateSize}")

                    continue

        # Return the largest event timestamp (convergenceTime), updated boolean, overhead bytes
        logging.debug(f"[{nodeName}] Final values: Convergence Time = {convergenceTime} | Updated = {updated} | Overhead = {overhead}")

        return convergenceTime, updated, overhead


    def parseIntfFailure(self, nodeName, line, recordTimestamp, intfName, convergenceTime):
        logging.debug(f"[{nodeName}] Failed interface detected: {line}")
        logging.debug(f"[{nodeName}] Failed interface timestamp: {recordTimestamp}")
        logging.debug(f"[{nodeName}] Failed interface name: {intfName}")

        # If the interface failure log came from the the node that lost an interface.
        if(self.isFailedNode(nodeName) and self.isFailedInterface(intfName)):
            # Record the time the interface actually failed
            self.updateIntfFailureTime(recordTimestamp)
            convergenceTime = max(convergenceTime, recordTimestamp)

            logging.debug(f"[{nodeName}] Successfully determined to be failed node.")

        # If the interface failure log came from the neighbor of the node that lost an interface.
        elif(self.isFailedNeighbor(nodeName) and self.isFailedNeighborInterface(intfName) and self.neighbor_intf_disabled is False):
            self.neighbor_intf_failed = True
            self.updateIntfFailureTime(recordTimestamp)
            convergenceTime = max(convergenceTime, recordTimestamp)

            logging.debug(f"[{nodeName}] Successfully determined to be failed neighbor node.")

        # If any other failure is detected, the test was a failure.
        else:
            logging.debug(f"[{nodeName}] Saw unexpected interface failure: {line}")
            raise Exception(f"Log error: Interface failure on node {nodeName}, Please check logs.")
        
        return convergenceTime
    
    
    def parseIntfTimeout(self, nodeName, line, recordTimestamp, intfName, convergenceTime):
        logging.debug(f"[{nodeName}] Disabled interface detected: {line}")
        logging.debug(f"[{nodeName}] Disabled interface timestamp: {recordTimestamp}")
        logging.debug(f"[{nodeName}] Disabled interface name: {intfName}")

        # If the interface disabled log came from the neighbor of the node that lost an interface.
        if(self.isFailedNeighbor(nodeName) and self.isFailedNeighborInterface(intfName) and self.neighbor_intf_failed is False):
            self.neighbor_intf_disabled = True
            convergenceTime = max(convergenceTime, recordTimestamp)

            logging.debug(f"[{nodeName}] Successfully determined to be failed neighbor node.")

        # If any other disabled interface is detected, the test was a failure.
        else:
            logging.debug(f"[{nodeName}] Saw unexpected interface disabled: {line}")
            raise Exception(f"Log error: Interface disabled on node {nodeName}, Please check logs.")

        return
    
    def updateIntfFailureTime(self, candidateFailureTime):
        '''
        Given the two failure times on both sides of a link, the failure time
        is the first recorded failure.
        '''

        # If not time has been recorded yet, it's the failure time.
        if(not self.intf_failure_time):
            self.intf_failure_time = candidateFailureTime
        
        # Otherwise, find the smaller of the two timestamps.
        else:
            self.intf_failure_time = min(self.intf_failure_time, candidateFailureTime)


        return