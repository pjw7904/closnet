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

# Types values for failure actions
FAILURE_DETECTION = 0
FAILURE_UPDATE = 1

# Timestamp information (Example timestamp in this format: 2024/04/30 04:09:33.947)
TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M:%S.%f"

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
   

def parseBGPLogFile(nodeName, logFile, experiment: ExperimentAnalysis):
    # Log record signatures for the types of records we're looking for
    INTF_FAILURE_LOG = "[SBFM4-2P25V] MESSAGE: ZEBRA_INTERFACE_DOWN" 
    RECV_UPDATE_PATTERN = r'rcvd\s+UPDATE.*wlen\s+(\d+)\s+attrlen\s+(\d+)\s+alen\s+(\d+)'

    action = None
    convergenceTime = 0
    overhead = 0

    with open(logFile) as file:
        for line in file:
            # If this is the node that lost an interface, find the time of that interface failure (starts convergence timing)
            if(experiment.isFailedNode(nodeName) and INTF_FAILURE_LOG in line):
                intfDownTimestamp = experiment.getEpochTime(line[:23]) # First 23 characters is the FRR log timestamp

                if(experiment.isValidLogRecord(intfDownTimestamp, useExperimentStartTime=True)):
                    return FAILURE_DETECTION, intfDownTimestamp, overhead                    
                else:
                    raise Exception(f"Log error: Failure detection timestamp {intfDownTimestamp} is outside of the experiment time period.")

            # If this is a node that received updated prefix information via BGP UPDATE messages, parse the message (consider for convergence timing)
            receivedBGPUpdate = re.search(RECV_UPDATE_PATTERN, line)
            if receivedBGPUpdate:
                updateTimestamp = experiment.getEpochTime(line[:23])

                wlen, attrlen, alen = map(int, receivedBGPUpdate.groups())

                if(any(val > 0 for val in (wlen, attrlen, alen)) and experiment.isValidLogRecord(updateTimestamp)):
                    action = FAILURE_UPDATE
                    convergenceTime = max(convergenceTime, updateTimestamp)
                    overhead += wlen + attrlen + alen + ETH_II_HEADER_LEN + IPV4_HEADER_LEN + TCP_HEADER_LEN + BGP_HEADER_LEN

    return action, convergenceTime, overhead

def runBGPExperimentAnalysis(logDirPath):
    # Define an experiment analysis object and setup initial values
    experiment = ExperimentAnalysis(logDirPath, EXPERIMENT_INFO_FILE)
    resultsFile = os.path.join(logDirPath, RESULTS_FILE)
    experiment.timestamp_format = TIMESTAMP_FORMAT

    # Open a log file and write results to it
    logging.basicConfig(
        filename=resultsFile,
        level=logging.INFO,
        format='%(message)s',
        filemode='w'
    )

    for logFile, nodeName in experiment.getLogFile(NODE_LOGS_DIR):
        experiment.number_of_nodes += 1
        nodeAction, nodeConvergenceTime, nodeOverhead = parseBGPLogFile(nodeName, logFile, experiment)

        #print(f"Action for {nodeName}: {'UPDATE' if nodeAction == 1 else nodeAction}")

        if(nodeAction == FAILURE_DETECTION):
            if(experiment.intf_failure_time != 0):
                raise Exception(f"There are multiple interface failures, please check logs.")
            else:
                experiment.intf_failure_time = nodeConvergenceTime
                experiment.number_of_updated_nodes += 1
        
        elif(nodeAction == FAILURE_UPDATE):
            experiment.convergence_times.append(nodeConvergenceTime)
            #print(f"\tConvergence time for {nodeName}: {nodeConvergenceTime}")

            if(nodeOverhead > 0):
                experiment.number_of_updated_nodes += 1

        experiment.overhead += nodeOverhead

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


if __name__ == "__main__":
    LOG_DIR = "/some/data/path"
    runBGPExperimentAnalysis(LOG_DIR)
