import os

def getResultsFile(directoryPath, metricDirectory):
    '''
    Iterate through a directory and returns the file path
    as well as the name of the file without its extension.
    '''

    directoryPath = os.path.join(directoryPath, metricDirectory)

    for fileName in os.listdir(directoryPath):
        filePath = os.path.join(directoryPath, fileName)
        
        # Separates the file name from its extension
        baseName = os.path.splitext(fileName)[0]

        # Only take the log files
        if fileName.endswith(".log"):
            yield filePath, baseName
    
    return


def getFailureInfo(logFile):
    '''
    Parse the experiment log file to determine
    where an interface failure occurred in the topology.
    '''
    
    failureInfo = {}

    # Iterate through each line in the file and store it as a KV pair
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
    '''
    Determine if the log file being analyzed belongs
    to the node where the interface failure occurred.
    '''
    
    return nodeName == failedNode


def isValidLogRecord(timestamp, intfFailureTime, experimentStopTime):
    return timestamp >= intfFailureTime and timestamp < experimentStopTime
