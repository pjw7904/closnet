# Core libraries
import os
import re
import logging

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
   

def writeResults(experiment: ExperimentAnalysis) -> None:
    '''
    Write the results of the experiment analysis to a file.
    '''
    
    logging.info("\n=== EXPERIMENT TIMESTAMPS ===")
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


def getFailedIntfName(line: str) -> str:
    '''
    Parse the interface name for a failure log record.
    '''

    # Parse out the interface name for failure confirmation
    match = INTF_FAILURE_PATTERN.search(line)
    if match:
        intfName = match.group(1)
    else:
        # Handle the case where there is no match
        intfName = None

    return intfName


def parseFailureLogRecord(nodeName, intfName, recordTimestamp, experiment: ExperimentAnalysis) -> None:
    # If the interface failure log came from the neighbor of the node that lost an interface.
    if(experiment.isFailedNeighbor(nodeName)):
        if(experiment.isFailedNeighborInterface(intfName)):
            logging.debug(f"[{nodeName}] Successfully determined to be failed neighbor node.")
        else:
            raise Exception("Log error: Multiple failures on failed neighbor, Please check logs.")

    # If the interface failure log came from the node that lost an interface.
    elif(experiment.isFailedNode(nodeName)):
        if(experiment.isFailedInterface(intfName)):
            experiment.intf_failure_time = recordTimestamp

            logging.debug(f"[{nodeName}] Successfully determined to be failed node.")
        else:
            raise Exception("Log error: Multiple failures on failed node, Please check logs.")

    # If the interface failure log came from any other node, there was an issue with the experiment.
    else:
        raise Exception(f"Log error: Interface failure on node {nodeName}, Please check logs.")
    
    return


def parseBGPLogFile(nodeName, logFile, experiment: ExperimentAnalysis):    
    convergenceTime = 0
    overhead = 0
    updated = False # Used for blast radius calculation. Nodes that are not updated are not part of the blast radius.

    with open(logFile) as file:
        for line in file:
            # If the log record is not within the experiment time frame, ignore it.
            recordTimestamp = experiment.getEpochTime(line[:23])
            if(not experiment.isValidLogRecord(recordTimestamp, useExperimentStartTime=True)):
                continue

            # The only valid failures within the experiment time frame are the specified node and its neighbor
            if(INTF_FAILURE_LOG in line):
                intfName = getFailedIntfName(line)

                logging.debug(f"[{nodeName}] Failed interface detected: {line.rstrip()}")
                logging.debug(f"[{nodeName}] Failed interface timestamp: {recordTimestamp}")
                logging.debug(f"[{nodeName}] Failed interface name: {intfName}")

                parseFailureLogRecord(nodeName, intfName, recordTimestamp, experiment)
                convergenceTime = max(convergenceTime, recordTimestamp)
                updated = True

            else:
                # If the node received updated prefix information via a BGP UPDATE message, parse the message
                receivedBGPUpdate = re.search(RECV_UPDATE_PATTERN, line)
                if receivedBGPUpdate:
                    wlen, attrlen, alen = map(int, receivedBGPUpdate.groups())

                    if(any(val > 0 for val in (wlen, attrlen, alen))):
                        convergenceTime = max(convergenceTime, recordTimestamp)
                        updated = True
                        overhead += wlen + attrlen + alen + ETH_II_HEADER_LEN + IPV4_HEADER_LEN + TCP_HEADER_LEN + BGP_HEADER_LEN

                        logging.debug(f"[{nodeName}] BGP UPDATE detected: {line.rstrip()}")
                        logging.debug(f"[{nodeName}] UPDATE timestamp: {recordTimestamp}")

    logging.debug(f"[{nodeName}] Final values: Convergence Time = {convergenceTime} | Updated = {updated} | Overhead = {overhead}")

    return convergenceTime, updated, overhead


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

    # Then, read through all of the nodes log files to see the reconvergence process (including the failed node as well)
    for logFile, nodeName in experiment.iterLogFiles(NODE_LOGS_DIR):
        logging.debug(f"\n*** Analyzing {nodeName} log file ({logFile}) ***")

        # Through the log records for this node, determine what its total message overhead is and the time of its final update
        nodeConvergenceTime, nodeWasUpdated, nodeOverhead = parseBGPLogFile(nodeName, logFile, experiment)

        # Update CONVERGENCE TIME metric data
        experiment.convergence_times.append(nodeConvergenceTime)

        # Update BLAST RADIUS metric data
        experiment.number_of_nodes += 1
        if(nodeWasUpdated):
            experiment.number_of_updated_nodes += 1

        # Update OVERHEAD metric data
        experiment.overhead += nodeOverhead

    # Write the analysis results to the results log file
    writeResults(experiment)


if __name__ == "__main__":
    # For further debugging. To run as a stand-alone script, remove the period (.) from the ExperimentAnalysis import statement
    LOG_DIR = "/home/pjw7904/closnet/logs/bgp/bgp_2_4_1-1_1741887879430"
    runBGPExperimentAnalysis(LOG_DIR, debugging=True)
