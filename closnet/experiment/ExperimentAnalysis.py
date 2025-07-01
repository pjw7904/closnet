# Core libraries
import os
import re
from abc import ABC, abstractmethod


class ExperimentAnalysis(ABC):
    EXPERIMENT_LOG_FILE = "experiment.log"
    INVALID_INTERFACE_FAILURE = 0
    VALID_INTERFACE_FAILURE = 1
    VALID_NEIGHBOR_FAILURE = 2

    HARD_LINK_FAILURE = 1
    SOFT_LINK_FAILURE = 2

    FAILED_LOG = 1
    DISABLED_LOG = 2

    def __init__(self, experimentDirPath, intfFailureTime=None):
        if not os.path.exists(experimentDirPath):
            raise FileNotFoundError("Experiment directory does not exist.")

        # Logging information
        self.directory = experimentDirPath
        self.timestamp_format = None

        # Experiment information
        self.experiment_type = None
        self.start_time = 0
        self.stop_time = 0
        self.intf_failure_time = intfFailureTime # The time an action was taken on an interface to fail/disable it.
        self.intf_failure_detection_time = None # The time the first node on the link noticed the failure via the chosen protocol. 

        self.failed_node = None
        self.failed_intf = None
        self.found_failed_intf = False

        self.neighbor_node = None
        self.failed_neighbor_intf = None
        self.found_failed_neighbor_intf = False

        self.number_of_nodes = 0
        self.number_of_updated_nodes = 0
        self.convergence_times = []

        self.traffic_included = False

        self.getExperimentInfo(os.path.join(experimentDirPath, self.EXPERIMENT_LOG_FILE))

        # Metrics
        self.overhead = 0
        self.blast_radius = 0.0
        self.reconvergence_time = 0
        self.traffic = []


    @abstractmethod
    def parseLogFile(self, nodeName, logFile):
        '''
        Parse the records of a node's protocol log file to calculate results.
        '''
        
        pass


    def getLogFile(self, directoryToParse, node, logFileExtension):
        '''
        Return the filepath for a node's log file.
        '''

        node += f"{logFileExtension}"
        return os.path.join(self.directory, directoryToParse, node)


    def iterLogFiles(self, directoryToParse, logFileExtension, priorityNodes=None):
        '''
        Iterate through a directory and returns the file path
        as well as the name of the file without its extension.
        '''

        if priorityNodes is None:
            priorityNodes = ()

        directoryPath = os.path.join(self.directory, directoryToParse)
        fileSeen = set()

        for node in priorityNodes:
            filePath = self.getLogFile(directoryToParse, node, logFileExtension)
            fileSeen.add(node)
            yield filePath, node

        for fileName in os.listdir(directoryPath):
            filePath = os.path.join(directoryPath, fileName)
            
            # Separates the file name from its extension
            baseName = os.path.splitext(fileName)[0]

            # Only take the log files
            if fileName.endswith(logFileExtension) and baseName not in fileSeen:
                yield filePath, baseName
        
        return


    def getExperimentInfo(self, logFile):
        '''
        Parse the experiment log file
        '''

        # Iterate through each line in the file and store the data
        with open(logFile) as file:
            for line in file:
                line = line.strip()

                if line.startswith("Failed node:"):
                    self.failed_node = line.split(":", 1)[1].strip()

                elif line.startswith("Failed neighbor:"):
                    self.neighbor_node = line.split(":", 1)[1].strip()

                elif line.startswith("Interface name:"):
                    self.failed_intf = line.split(":", 1)[1].strip()

                elif line.startswith("Neighbor interface name:"):
                    self.failed_neighbor_intf = line.split(":", 1)[1].strip()

                elif line.startswith("Experiment type:"):
                    match = re.match(r"Experiment type: (.+?) link failure", line)
                    if match:
                         failureType = match.group(1)
                         self.experiment_type = self.SOFT_LINK_FAILURE if failureType.strip() == "soft" else self.HARD_LINK_FAILURE
                    else:
                        raise Exception("Unknown failure type.")

                elif line.startswith("Experiment start time:"):
                    self.start_time = int(line.split(":", 1)[1].strip())

                elif line.startswith("Experiment stop time:"):
                    self.stop_time = int(line.split(":", 1)[1].strip())

                elif line.startswith("Traffic included:"):
                    value = line.split(":", 1)[1].strip()
                    self.traffic_included = value.lower() == "true"

        return


    def isFailedNode(self, node):
        '''
        Determine if the log file being analyzed belongs
        to the node where the interface failure occurred.
        '''

        return node == self.failed_node


    def isFailedInterface(self, interface):
        '''
        Determine if the interface being failed
        is the correct interface from the experiment
        '''

        return interface == self.failed_intf


    def isFailedNeighbor(self, node):
        '''
        Determine if the log file being analyzed belongs
        to the neighbor of the node where the interface 
        failure occurred.
        '''

        return node == self.neighbor_node
    
    def isFailedNeighborInterface(self, interface):
        '''
        Determine if the interface being failed
        is the correct neighbor interface from the experiment
        '''

        return interface == self.failed_neighbor_intf
    

    def parseIntfFailure(self, nodeName, recordTimestamp, intfName, convergenceTime, logType):
        result = None

        # If there is an interface failure that doesn't match how it was failed, the experiment was unsucessful.
        if((self.experiment_type == self.SOFT_LINK_FAILURE and logType == self.FAILED_LOG) or
           (self.experiment_type == self.HARD_LINK_FAILURE and logType == self.DISABLED_LOG)):
            result = self.INVALID_INTERFACE_FAILURE

        # If the interface failure log came from the the node that lost an interface.
        elif(self.isFailedNode(nodeName) and 
           self.isFailedInterface(intfName) and 
           self.found_failed_intf is False):
            
            self.found_failed_intf = True
            result = self.VALID_INTERFACE_FAILURE

        # If the interface failure log came from the neighbor of the node that lost an interface.
        elif(self.isFailedNeighbor(nodeName) and
             self.isFailedNeighborInterface(intfName) and
             self.found_failed_neighbor_intf is False):

            self.found_failed_neighbor_intf = True
            result = self.VALID_NEIGHBOR_FAILURE

        else:
            result = self.INVALID_INTERFACE_FAILURE

        # As long as its a valid failure, update the convergence time
        if(result != self.INVALID_INTERFACE_FAILURE):
            self.updateIntfFailureTime(recordTimestamp)
            convergenceTime = max(convergenceTime, recordTimestamp)

        return result, convergenceTime
    

    def updateIntfFailureTime(self, candidateFailureTime):
        '''
        Given the two failure times on both sides of a link, the failure time
        is the first recorded failure.
        '''

        # If no time has been recorded yet, it's the failure time.
        if(self.intf_failure_detection_time is None):
            self.intf_failure_detection_time = candidateFailureTime
        
        # Otherwise, find the smaller of the two timestamps.
        else:
            self.intf_failure_detection_time = min(self.intf_failure_detection_time, candidateFailureTime)

        # For hard link failures, the detection of the failure and the time it went down is the same.
        if(self.experiment_type == self.HARD_LINK_FAILURE):
            self.intf_failure_time = self.intf_failure_detection_time

        return
        

    def isValidLogRecord(self, timestamp, useExperimentStartTime=False):
        '''
        Determine if the log record being analyzed is within
        the time period of the experiment. Timestamps must
        be in epoch formatting.
        '''

        definedStartingTime = self.start_time if useExperimentStartTime else self.intf_failure_detection_time

        return definedStartingTime <= timestamp <= self.stop_time


    def getReconvergenceTime(self):
        if(self.intf_failure_time is None):
            raise Exception("No interface failure recorded. Please check logs.")
        
        if(self.intf_failure_detection_time is None):
            raise Exception("No interface failure detected. Please check logs.")

        if(not self.found_failed_intf and not self.found_failed_neighbor_intf):
            raise Exception("The interface failure on both ends of the link was not found. Please check logs.")

        if(not self.convergence_times):
            raise Exception("No convergence logs found. Please check logs.")
    
        lastChangeTimestamp = max(self.convergence_times)
        
        # The calculation looks at the actual time of failure, thus it includes failure time ---> then time of detection --> then time to reconverge all other nodes
        return lastChangeTimestamp - self.intf_failure_time
    

    def getFinalConvergenceTimestamp(self):
        return max(self.convergence_times)


    def getBlastRadius(self):
        if(not self.number_of_nodes):
            raise Exception("No nodes recorded. Please check logs.")

        return (self.number_of_updated_nodes/self.number_of_nodes) * 100
