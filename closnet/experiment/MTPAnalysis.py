import os
import re
import logging

# Topology and experiment information
LOG_DIR_PATH = "/home/pjw7904/MTP-Mininet/logs/mtp/mtp_2_4_1-1_1740540503602"
DOWNTIME_DIR = "downtime"
CONVERGENCE_DIR = "convergence"
RESULTS_FILE = os.path.join(LOG_DIR_PATH, "results.log")

NETWORK_NODE_PREFIXES = "T,S,L"
COMPUTE_NODE_PREFIXES = "C"

# Types values for failure actions
CANNOT_DETERMINE_CONVERGENCE_TIME = -1
FAILURE_DETECTION = 0
FAILURE_UPDATE = 1


def getResultsFile(metricDirectory):
    directoryPath = os.path.join(LOG_DIR_PATH, metricDirectory)

    for fileName in os.listdir(directoryPath):
        filePath = os.path.join(directoryPath, fileName)

        # Only take the log files
        if(".log" in fileName):
            yield filePath
    
    return


def getDownTime(logFile):
    '''
    Read the first line of a downtime file, which must be the time in epoch formatting.
    '''

    with open(logFile) as file:
        return int(file.readline())


def parseTimestamp(line):
    '''
    Get the time of the failure message.
    '''
    return int(line.split(" ")[6].replace(",",""))


def parseOverhead(line, timestamp):
    '''
    Get the size of the failure message.
    '''
    overhead = int(line.split("=")[1]) if timestamp < testStopTime else 0

    return overhead


def getOverhead(logFile):
    with open(logFile) as f:
        line = f.readline()
        size = 0
    
        while line:
            if "FAILURE UPDATE message received" in line:
                time = parseTimestamp(line)
                size += parseOverhead(f.readline(), time)
    
            line = f.readline()

    return size


def getNodeConvergenceTime(logFile):
    """
    Parse the log file to determine the node's convergence time.
    """

    # The detection pattern assumes the timestamp is the last group of digits in the line.
    detection_pattern = re.compile(r"Detected a failure.*?(\d+)\s*$")

    # The update pattern extracts a group of digits (which may have a trailing comma) after the message.
    update_pattern = re.compile(r"FAILURE UPDATE message received.*?(\d+),?")

    with open(logFile) as f:
        for line in f:
            if "Detected a failure" in line:
                match = detection_pattern.search(line)

                if match:
                    timestamp = int(match.group(1))

                    if timestamp < failureTime:
                        raise Exception(f"Log error: 'Detected a failure' timestamp {timestamp} is before the interface failure time {failureTime}.")

                    if timestamp < testStopTime:
                        return FAILURE_DETECTION, timestamp
                    
            elif "FAILURE UPDATE message received" in line:
                match = update_pattern.search(line)
                
                if match:
                    timestamp = int(match.group(1))

                    if timestamp < failureTime:
                        raise Exception(f"Log error: 'FAILURE UPDATE' timestamp {timestamp} is before the interface failure time {failureTime}.")

                    if timestamp < testStopTime:
                        return FAILURE_UPDATE, timestamp

    return CANNOT_DETERMINE_CONVERGENCE_TIME, CANNOT_DETERMINE_CONVERGENCE_TIME


# STEP 1: Parse and record timestamps for downtime (interface, network)
for logFile in getResultsFile(DOWNTIME_DIR):
    if("experiment_stop" in logFile): # Determine what the test stoptime was.
        testStopTime = getDownTime(logFile)

    elif("intf_down" in logFile): # Determine when the interface failure occurred.
        failureTime = getDownTime(logFile)
    
    else:
        logging.info(f"Unknown file {logFile}")

# Open a log file and write results to it
logging.basicConfig(
    filename=RESULTS_FILE,
    level=logging.INFO,
    format='%(message)s',
    filemode='w'
)

logging.info("=== EXPERIMENT TIMESTAMPS ===")
logging.info(f"Interface failure timestamp: {failureTime}\nExperiment teardown timestamp: {testStopTime}\n")


# Control Overhead values
totalOverhead = 0

# Blast Radius values
totalNodeCount = 0
effectedNodeCount = 2 # Starts at 2 for the 2 nodes that lost a link. They won't have any updates.

for logFile in getResultsFile(CONVERGENCE_DIR):
    # Blast radius value updates
    totalNodeCount += 1
    
    if(os.path.getsize(logFile) > 0):
        nodeOverhead = getOverhead(logFile)

        if(nodeOverhead > 0):
            effectedNodeCount += 1

        # Add node's overhead to total overhead
        totalOverhead += nodeOverhead
    
    else:
        logging.info(f"Log file {logFile} is empty")

# Calculate blast radius as the fraction of total nodes that received updates
blastRadius = (effectedNodeCount/totalNodeCount) * 100

# Print results
logging.info("=== OVERHEAD ===")
logging.info(f"{totalOverhead} bytes\n")

logging.info("=== BLAST RADIUS ===")
logging.info(f"{blastRadius:.2f}% of nodes received VID failure information.")
logging.info(f"\tNodes receiving updated information: {effectedNodeCount}\n\tTotal nodes: {totalNodeCount}\n")

# Default starting values for the timing range
failureDetectionTimestamp = -1
finalFailureRecoveryTimestamp = -1

for logFile in getResultsFile(CONVERGENCE_DIR):
    if(os.path.getsize(logFile) > 0):
        failureType, failureTimestamp = getNodeConvergenceTime(logFile)

        if(failureType == FAILURE_DETECTION):
            if(failureDetectionTimestamp > 0):
                raise Exception("Multiple begin times, please check log")
            failureDetectionTimestamp = failureTimestamp

        elif(failureType == FAILURE_UPDATE):
            finalFailureRecoveryTimestamp = max(finalFailureRecoveryTimestamp, failureTimestamp)

convergenceTime = finalFailureRecoveryTimestamp - failureDetectionTimestamp

# Print results
logging.info("=== CONVERGENCE TIME ===")
logging.info(f"Final failure update time: {finalFailureRecoveryTimestamp}\nFailure Detection time: {failureDetectionTimestamp}")
logging.info(f"Convergence time: {convergenceTime} milliseconds")
