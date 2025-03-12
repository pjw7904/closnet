import os
import re
import logging
from datetime import datetime

# Topology and experiment information
LOG_DIR_PATH = "/home/pjw7904/closnet/logs/bgp/bgp_2_4_1-1_1741761296707"
DOWNTIME_DIR = "downtime"
CONVERGENCE_DIR = "convergence"
RESULTS_FILE = os.path.join(LOG_DIR_PATH, "results.log")

# Types values for failure actions
FAILURE_DETECTION = 0
FAILURE_UPDATE = 1

# Timestamp information
TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M:%S.%f" # Example timestamp in this format: 2024/04/30 04:09:33.947

# Message header sizes
'''
BGP UPDATE message structure:
+-----------+ +-----------+ +-----------+ +-------------+ +-------------+  
| ETH II    | | IPV4      | | TCP       | | BGP MESSAGE | | BGP UPDATE  | 
+-----------+ +-----------+ +-----------+ +-------------+ +-------------+ 
'''
ETH_II_HEADER_LEN = 14
IPV4_HEADER_LEN = 20
TCP_HEADER_LEN = 20
BGP_HEADER_LEN = 23 # 19 bytes for the general BGP header, 2 bytes for the withdraw length, 2 bytes for the path attribute length 


def getResultsFile(metricDirectory):
    directoryPath = os.path.join(LOG_DIR_PATH, metricDirectory)

    for fileName in os.listdir(directoryPath):
        filePath = os.path.join(directoryPath, fileName)
        
        # Separates the file name from its extension
        baseName = os.path.splitext(fileName)[0]

        # Only take the log files
        if fileName.endswith(".log"):
            yield filePath, baseName
    
    return


def getFailureInfo(logFile):
    # Dictonary to store failure info
    failureInfo = {}

    with open(logFile) as file:
        for line in file:
            line = line.strip()

            if line.startswith("Failed node:"):
                failureInfo["failed_node"] = line.split(":", 1)[1].strip()

            elif line.startswith("Failed neighbor:"):
                failureInfo["failed_neighbor"] = line.split(":", 1)[1].strip()

            elif line.startswith("Interface name:"):
                failureInfo["interface_name"] = line.split(":", 1)[1].strip()

            elif line.startswith("Interface failure timestamp:"):
                # convert numeric values to int
                failureInfo["interface_failure_timestamp"] = int(line.split(":", 1)[1].strip())

            elif line.startswith("Experiment stop timestamp:"):
                failureInfo["experiment_stop_timestamp"] = int(line.split(":", 1)[1].strip())

    return failureInfo


def isFailedNode(nodeName, failedNode):
    return nodeName == failedNode


def getEpochTime(originalTimestamp):
    '''
    Return a epoch (unix) timestamp based on the original timestamp.
    '''

    datetimeFormat = datetime.strptime(originalTimestamp, TIMESTAMP_FORMAT)
    return int(datetime.timestamp(datetimeFormat) * 1000) # Reduce precision by moving milliseconds into main timestamp.


def isWithinExperimentTimeRange(timestamp, interfaceFailureTimestamp, experimentStopTimestamp):
    return timestamp >= interfaceFailureTimestamp and timestamp < experimentStopTimestamp


def parseBGPLogFile(nodeName, logFile, failureInfo):
    # Log record signatures for the types of records we're looking for
    INTF_FAILURE_LOG = "[SBFM4-2P25V] MESSAGE: ZEBRA_INTERFACE_DOWN" 
    RECV_UPDATE_PATTERN = r'rcvd\s+UPDATE.*wlen\s+(\d+)\s+attrlen\s+(\d+)\s+alen\s+(\d+)'
    
    # Check if this log is for the node that lost an interface
    failedNode = isFailedNode(nodeName, failureInfo["failed_node"])

    action = None
    convergenceTime = 0
    overhead = 0
    with open(logFile) as file:
        for line in file:
            # This is the node that lost an interface, find the time of that interface failure
            if(failedNode and INTF_FAILURE_LOG in line):
                intfDownTimestamp = getEpochTime(line[:23]) # First 23 characters is the FRR log timestamp

                if intfDownTimestamp < failureInfo["interface_failure_timestamp"]:
                    raise Exception(f"Log error: Failure detection timestamp {intfDownTimestamp} is before the interface failure time {failureInfo['interface_failure_timestamp']}.")

                if intfDownTimestamp < failureInfo["experiment_stop_timestamp"]:
                    return FAILURE_DETECTION, intfDownTimestamp, overhead
                else:
                    raise Exception(f"Log error: Failure detection timestamp {intfDownTimestamp} is after the experiment end time {failureInfo['experiment_stop_timestamp']}.")

            # This is a node that received updated prefix information via BGP UPDATE messages, parse those messages.
            receivedBGPUpdate = re.search(RECV_UPDATE_PATTERN, line)
            if receivedBGPUpdate:
                updateTimestamp = getEpochTime(line[:23])

                wlen, attrlen, alen = map(int, receivedBGPUpdate.groups())

                if any(val > 0 for val in (wlen, attrlen, alen)) and isWithinExperimentTimeRange(updateTimestamp, failureInfo["interface_failure_timestamp"], failureInfo["experiment_stop_timestamp"]):
                    action = FAILURE_UPDATE
                    convergenceTime = max(convergenceTime, updateTimestamp)
                    overhead += wlen + attrlen + alen + ETH_II_HEADER_LEN + IPV4_HEADER_LEN + TCP_HEADER_LEN + BGP_HEADER_LEN

    return action, convergenceTime, overhead

def main():
    # Parse failure information and save it
    failureInfo = {}
    for logFile, _ in getResultsFile(DOWNTIME_DIR):
        failureInfo = getFailureInfo(logFile)

    if not failureInfo:
        raise Exception("Experiment results does not contain failure information.")

    # Parse BGP log information to determine experiment results
    totalOverhead = -1
    blastRadius = -1
    convergenceTimes = [] # Store all of the node's convergence time's.
    startTime = 0
    totalNodeCount = 0
    updatedNodeCount = 0

    startTime = 0 # Time when the interface went down.
    for logFile, nodeName in getResultsFile(CONVERGENCE_DIR):
        totalNodeCount += 1
        nodeAction, nodeConvergenceTime, nodeOverhead = parseBGPLogFile(nodeName, logFile, failureInfo)

        print(f"Action for {nodeName}: {'UPDATE' if nodeAction == 1 else nodeAction}")

        if(nodeAction == FAILURE_DETECTION):
            if(startTime != 0):
                raise Exception(f"There are multiple experiment  start times, please check logs.")
            else:
                startTime = nodeConvergenceTime
                updatedNodeCount += 1
        
        elif(nodeAction == FAILURE_UPDATE):
            convergenceTimes.append(nodeConvergenceTime)
            print(f"\tConvergence time for {nodeName}: {nodeConvergenceTime}")

            if(nodeOverhead > 0):
                updatedNodeCount += 1
        
        totalOverhead += nodeOverhead

    if(startTime == 0):
        raise Exception(f"No interface failure recorded. Please check logs.")
    if(not convergenceTimes):
        raise Exception(f"No convergence logs found. Please check logs.")

    # Determine reconvergence time
    lastChangeTimestamp = max(convergenceTimes)
    reconvergenceTime = lastChangeTimestamp - startTime

    # Determine blast radius
    blastRadius = (updatedNodeCount/totalNodeCount) * 100

    print(f"\nDown/Start time: {startTime}")
    print(f"Overhead: {totalOverhead} bytes")
    print(f"\nBlast radius: {blastRadius:.2f}% of nodes received updated prefix information.")
    print(f"\tNodes receiving updated information: {updatedNodeCount}\n\tTotal nodes: {totalNodeCount}")
    print(f"Reconvergence time: {reconvergenceTime} milliseconds")

if __name__ == "__main__":
    main()
