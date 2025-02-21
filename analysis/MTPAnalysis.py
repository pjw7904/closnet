LOG_DIR_PATH = "/home/pjw7904/MTP-Mininet/logs/mtp/mtp_2_4_1-1_1739380399451"
NETWORK_NODE_PREFIXES = "T,S,L"
COMPUTE_NODE_PREFIXES = "C"

import os

def getResultsFile(metricDirectory):
    directoryPath = os.path.join(LOG_DIR_PATH, metricDirectory)

    for fileName in os.listdir(directoryPath):
        filePath = os.path.join(directoryPath, fileName)

        # Only take the log files
        if(".log" in fileName):
            yield filePath
    
    return


def getIntfDownTime(logFile):
    '''
    Read the first line of the interface downtime file, which must be the time in epoch formatting.
    '''

    with open(logFile) as file:
        return int(file.readline())


def getTestStopTime(logFile):
    '''
    Find the stoptime for each node and determine the one that stopped first. That time is the end of the test.
    '''
    testStopTime = 0
    
    with open(logFile) as file:
        lines = file.readlines()

        for line in lines:
            nodeStopTime = int(line.split(":")[1])
            testStopTime = nodeStopTime if nodeStopTime < testStopTime or testStopTime == 0 else testStopTime
    
    return testStopTime

# Analyze each file in the downtime subdirectory
for logFile in getResultsFile("downtime"):
    if("nodes_down" in logFile): # Determine what the test stoptime was.
        testStopTime = getTestStopTime(logFile)
    elif("intf_down" in logFile): # Determine when the interface failure occurred.
        failureTime = getIntfDownTime(logFile)
    else:
        print(f"Unknown file {logFile}")

print(f"Interface failure timestamp: {failureTime}\nTest stop timestamp: {testStopTime}")


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

# Control Overhead values
totalOverhead = 0

# Blast Radius values
totalNodeCount = 0
effectedNodeCount = 2 # Starts at 2 for the 2 nodes that lost a link. They won't have any updates.

for logFile in getResultsFile("convergence"):
    # Blast radius value updates
    totalNodeCount += 1
    
    if(os.path.getsize(logFile) > 0):
        nodeOverhead = getOverhead(logFile)

        if(nodeOverhead > 0):
            effectedNodeCount += 1

        # Add node's overhead to total overhead
        totalOverhead += nodeOverhead
    
    else:
        print(f"Log file {logFile} is empty")

# Calculate blast radius as the fraction of total nodes that received updates
blastRadius = (effectedNodeCount/totalNodeCount) * 100

# Print results
print(f"Overhead: {totalOverhead} bytes")
print(f"\nBlast radius: {blastRadius:.2f}% of nodes received VID failure information.")
print(f"\tNodes receiving updated information: {effectedNodeCount}\n\tTotal nodes: {totalNodeCount}")

# Types values for failure actions
FAILURE_DETECTION = 0
FAILURE_UPDATE = 1

def getNodeConvergenceTime(logFile):
    with open(logFile) as f:
        line = f.readline()
    
        while line:
            token = line.split(" ")
            
            if "Detected a failure" in line:            
                return 0,int(token[len(token)-1])
            
            elif "FAILURE UPDATE message received" in line:
                time = int(token[6].replace(",",""))
    
                if(time < testStopTime):
                    return 1,int(time)
            
            line = f.readline()
        
    return -1,-1

# Default starting values for the timing range
failureDetectionTimestamp = -1
finalFailureRecoveryTimestamp = -1

for logFile in getResultsFile("convergence"):
    if(os.path.getsize(logFile) > 0):
        failureType, failureTimestamp = getNodeConvergenceTime(logFile)

        if(failureType == FAILURE_DETECTION):
            if(failureDetectionTimestamp > 0):
                raise Exception("Multiple begin times, please check log")
            failureDetectionTimestamp = failureTimestamp

        elif(failureType == FAILURE_UPDATE):
            finalFailureRecoveryTimestamp = max(finalFailureRecoveryTimestamp, failureTimestamp)

convergenceTime = finalFailureRecoveryTimestamp - failureDetectionTimestamp
print(f"Final failure update time: {finalFailureRecoveryTimestamp}\nFailure Detection time: {failureDetectionTimestamp}")
print(f"Convergence time: {convergenceTime} ms")
