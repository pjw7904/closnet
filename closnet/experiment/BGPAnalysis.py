# Core libraries
import os
import re
import logging
from datetime import datetime

# Custom libraries
from .ExperimentAnalysis import ExperimentAnalysis

# Constants
# File & directory information
EXPERIMENT_INFO_FILE = "experiment.log"
RESULTS_FILE = "results.log"
NODE_LOGS_DIR = "nodes"

# Timestamp information (Example timestamp in this format: 2024/04/30 04:09:33.947)
TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M:%S.%f"

# Patterns to match in log file records
INTF_FAILURE_PATTERN = re.compile(r"ZEBRA_INTERFACE_DOWN\s+(\S+)\s+vrf")
RECV_UPDATE_PATTERN = re.compile(r'rcvd\s+UPDATE.*wlen\s+(\d+)\s+attrlen\s+(\d+)\s+alen\s+(\d+)')
INTF_FAILURE_LOG = "[SBFM4-2P25V] MESSAGE: ZEBRA_INTERFACE_DOWN" 

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
   

def writeResults(experiment: ExperimentAnalysis):
    logging.info("=== EXPERIMENT TIMESTAMPS ===")
    logging.info(f"Experiment start time: {experiment.start_time}\nInterface failure time: {experiment.intf_failure_time}\nExperiment stop timestamp: {experiment.stop_time}\n")

    logging.info("=== OVERHEAD ===")
    logging.info(f"{experiment.overhead} bytes\n")

    logging.info("=== BLAST RADIUS ===")
    logging.info(f"{experiment.getBlastRadius():.2f}% of nodes received updated prefix information.")
    logging.info(f"\tNodes receiving updated information: {experiment.number_of_updated_nodes}\n\tTotal nodes: {experiment.number_of_nodes}\n")

    logging.info("=== CONVERGENCE TIME ===")
    logging.info(f"Final failure update time: {experiment.getFinalConvergenceTimestamp()}\n")
    logging.info(f"Convergence time: {experiment.getReconvergenceTime()} milliseconds")

    return


def getFailedIntfInfo(line, experiment):
    '''
    Parse the interface failure time and interface name for a failure log record.
    '''

    intfDownTimestamp = experiment.getEpochTime(line[:23]) # First 23 characters is the FRR log timestamp

    # Parse out the interface name for failure confirmation
    match = INTF_FAILURE_PATTERN.search(line)
    if match:
        intfName = match.group(1)
    else:
        # Handle the case where there is no match
        intfName = None

    return intfName, intfDownTimestamp


def parseFailedNodeLogFile(nodeName, logFile, experiment: ExperimentAnalysis):
    if(not experiment.isFailedNode(nodeName)):
        raise Exception(f"Log error: Failed node is incorrect for analysis.")
    
    foundIntfFailureLog = False

    with open(logFile) as file:
        for line in file:
            # Validate and find the time of that interface failure (starts convergence timing)
            if(INTF_FAILURE_LOG in line):
                intfName, intfDownTimestamp = getFailedIntfInfo(line, experiment)

                logging.debug(f"[{nodeName}] Failed interface detected: {line.rstrip()}")
                logging.debug(f"[{nodeName}] Failed interface timestamp: {intfDownTimestamp}")
                logging.debug(f"[{nodeName}] Failed interface name: {intfName}")

                if(experiment.isValidLogRecord(intfDownTimestamp, useExperimentStartTime=True) and experiment.isFailedInterface(intfName)):
                    experiment.intf_failure_time = intfDownTimestamp
                    foundIntfFailureLog = True

                    logging.debug(f"[{nodeName}] Successfully determined to be failed node.")
                    logging.debug(f"[{nodeName}] Final values: convergence time = {intfDownTimestamp} | Overhead = N/A")
                    
                    return foundIntfFailureLog
                     
                else:
                    raise Exception(f"Log error: Interface failure found on node {nodeName} is invalid. Please check the logs.")
                
    return foundIntfFailureLog


def parseBGPLogFile(nodeName, logFile, experiment: ExperimentAnalysis):    
    convergenceTime = 0
    overhead = 0

    # Determine if the node being analyzed is the node with the interface failure, or is the neighbor of that node on the failed link.
    failedNode = True if experiment.isFailedNode(nodeName) else False
    failedNeighbor = True if experiment.isFailedNeighbor(nodeName) else False

    with open(logFile) as file:
        for line in file:
            # If the log record is not within the experiment time frame, ignore it.
            recordTimestamp = experiment.getEpochTime(line[:23])
            if(not experiment.isValidLogRecord(recordTimestamp, useExperimentStartTime=True)):
                continue

            # Make sure that there aren't multiple interface failures within the experiment time range, unless it's the neighbor node
            if(INTF_FAILURE_LOG in line):
                if(failedNeighbor):
                    intfName, intfDownTimestamp = getFailedIntfInfo(line, experiment)

                    logging.debug(f"[{nodeName}] Failed interface detected: {line.rstrip()}")
                    logging.debug(f"[{nodeName}] Failed interface timestamp: {intfDownTimestamp}")
                    logging.debug(f"[{nodeName}] Failed interface name: {intfName}")

                    if(experiment.isValidLogRecord(intfDownTimestamp, useExperimentStartTime=True) and experiment.isFailedNeighborInterface(intfName)):
                        logging.debug(f"[{nodeName}] Successfully determined to be failed neighbor node.")
                        continue
                    else:
                        raise Exception("Log error: Multiple failures on failed neighbor, Please check logs.")

                elif(failedNode):
                    intfName, intfDownTimestamp = getFailedIntfInfo(line, experiment)

                    if(intfDownTimestamp == experiment.intf_failure_time and experiment.isFailedInterface(intfName)):
                        logging.debug(f"[{nodeName}] Found the correct interface failure log again, ignoring.")
                        continue
                    else:
                        raise Exception("Log error: Multiple failures on failed node, Please check logs.")
                else:
                    raise Exception(f"Log error: Interface failure on node {nodeName}, Please check logs.")

            # If the node received updated prefix information via a BGP UPDATE message, parse the message (consider for convergence timing)
            receivedBGPUpdate = re.search(RECV_UPDATE_PATTERN, line)
            if receivedBGPUpdate:
                wlen, attrlen, alen = map(int, receivedBGPUpdate.groups())

                if(any(val > 0 for val in (wlen, attrlen, alen))):
                    convergenceTime = max(convergenceTime, recordTimestamp)
                    overhead += wlen + attrlen + alen + ETH_II_HEADER_LEN + IPV4_HEADER_LEN + TCP_HEADER_LEN + BGP_HEADER_LEN

                    logging.debug(f"[{nodeName}] BGP UPDATE detected: {line.rstrip()}")
                    logging.debug(f"[{nodeName}] UPDATE timestamp: {recordTimestamp}")

    logging.debug(f"[{nodeName}] Final values: Convergence Time = {convergenceTime} | Overhead = {overhead}")
    return convergenceTime, overhead


def runBGPExperimentAnalysis(logDirPath, debugging=False):
    # Define an experiment analysis object and setup initial values
    experiment = ExperimentAnalysis(logDirPath, EXPERIMENT_INFO_FILE)
    resultsFile = os.path.join(logDirPath, RESULTS_FILE)
    experiment.timestamp_format = TIMESTAMP_FORMAT

    # Open a log file to record results of the analysis
    logging.basicConfig(
        filename=resultsFile,
        level=logging.DEBUG if debugging else logging.INFO,
        format='%(message)s',
        filemode='w'
    )

    logging.debug("=== DEBUGGING ===")

    # Read through the failed node's log first to get a time for the start of the reconvergence process.
    logging.debug(f"\n*** Analyzing {experiment.failed_node} log file for interface failure detection ***")
    failedNodeLogFilePath = experiment.getLogFile(NODE_LOGS_DIR, experiment.failed_node)
    foundIntfFailureLog = parseFailedNodeLogFile(experiment.failed_node, failedNodeLogFilePath, experiment)

    if(not foundIntfFailureLog):
        raise Exception("Log error: Failed node's interface failure log cannot be located. Please check logs.")

    # Mark that node as updated
    experiment.number_of_nodes += 1
    experiment.number_of_updated_nodes += 1

    # Then, read through all of the nodes log files to see the reconvergence process (including the failed node as well)
    for logFile, nodeName in experiment.iterLogFiles(NODE_LOGS_DIR):
        logging.debug(f"\n*** Analyzing {nodeName} log file ({logFile}) ***")

        # Through the log records for this node, determine what its total message overhead is and the time of its final update
        nodeConvergenceTime, nodeOverhead = parseBGPLogFile(nodeName, logFile, experiment)

        # Add the node results to the appropriate metric collection structures
        experiment.convergence_times.append(nodeConvergenceTime)
        experiment.overhead += nodeOverhead

        # If the node received one or more BGP UPDATE messages, it is part of the reconvergence blast radius. 
        if(nodeOverhead > 0):
            experiment.number_of_updated_nodes += 1

        # Don't double-count the failed node
        if not experiment.isFailedNode(nodeName):
            experiment.number_of_nodes += 1

    # Write the analysis results to the results log file
    writeResults(experiment)


if __name__ == "__main__":
    LOG_DIR = "/home/pjw7904/closnet/logs/bgp/bgp_2_4_1-1_1741887879430"
    runBGPExperimentAnalysis(LOG_DIR, debugging=True)
