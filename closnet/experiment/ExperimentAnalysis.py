# Core libraries
import os
from abc import ABC, abstractmethod


class ExperimentAnalysis(ABC):
    EXPERIMENT_LOG_FILE = "experiment.log"

    def __init__(self, experimentDirPath):
        if not os.path.exists(experimentDirPath):
            raise FileNotFoundError("Experiment directory does not exist.")

        # Logging information
        self.directory = experimentDirPath
        self.timestamp_format = None

        # Experiment information
        self.start_time = 0
        self.stop_time = 0
        self.intf_failure_time = 0

        self.failed_node = None
        self.neighbor_node = None

        self.failed_intf = None
        self.neighbor_intf = None

        self.number_of_nodes = 0
        self.number_of_updated_nodes = 0
        self.convergence_times = []

        self.getExperimentInfo(os.path.join(experimentDirPath, self.EXPERIMENT_LOG_FILE))

        # Metrics
        self.overhead = 0
        self.blast_radius = 0.0
        self.reconvergence_time = 0


    @abstractmethod
    def parseLogFile(self, nodeName, logFile):
        '''
        Parse the records of a node's protocol log file to calculate results.
        '''
        
        pass


    def getLogFile(self, directoryToParse, node):
        '''
        Return the filepath for a node's log file.
        '''

        node += ".log"
        return os.path.join(self.directory, directoryToParse, node)


    def iterLogFiles(self, directoryToParse):
        '''
        Iterate through a directory and returns the file path
        as well as the name of the file without its extension.
        '''

        directoryPath = os.path.join(self.directory, directoryToParse)

        for fileName in os.listdir(directoryPath):
            filePath = os.path.join(directoryPath, fileName)
            
            # Separates the file name from its extension
            baseName = os.path.splitext(fileName)[0]

            # Only take the log files
            if fileName.endswith(".log"):
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
                    self.neighbor_intf = line.split(":", 1)[1].strip()

                elif line.startswith("Experiment start time:"):
                    self.start_time = int(line.split(":", 1)[1].strip())

                elif line.startswith("Experiment stop time:"):
                    self.stop_time = int(line.split(":", 1)[1].strip())

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

        return interface == self.neighbor_intf


    def isValidLogRecord(self, timestamp, useExperimentStartTime=False):
        '''
        Determine if the log record being analyzed is within
        the time period of the experiment. Timestamps must
        be in epoch formatting.
        '''

        if(useExperimentStartTime):
            return timestamp > self.start_time and timestamp < self.stop_time
        else:
            return timestamp > self.intf_failure_time and timestamp < self.stop_time


    def getReconvergenceTime(self):
        if(not self.intf_failure_time):
            raise Exception("No interface failure recorded. Please check logs.")

        if(not self.convergence_times):
            raise Exception("No convergence logs found. Please check logs.")
    
        lastChangeTimestamp = max(self.convergence_times)
        
        return lastChangeTimestamp - self.intf_failure_time
    

    def getFinalConvergenceTimestamp(self):
        return max(self.convergence_times)


    def getBlastRadius(self):
        if(not self.number_of_nodes):
            raise Exception("No nodes recorded. Please check logs.")

        return (self.number_of_updated_nodes/self.number_of_nodes) * 100
