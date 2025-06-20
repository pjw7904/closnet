# Core libraries
import subprocess
import shutil
import logging
import os
import signal
from pathlib import Path
from time import sleep, time_ns

# Custom libraries
from closnet.experiment.ExperimentAnalysis import ExperimentAnalysis
from closnet.TrafficGenerator import analyzeTraffic

# Constants
TRAFFIC_GEN = os.path.join(os.path.dirname(__file__), "..", "TrafficGenerator.py")
NUM_TEST_PACKETS_TO_SEND = 1000
PROTOCOL_LOG_FILE_PATTERN = "*.log"
TRAFFIC_LOG_FILE_PATTERN = "*.pcapng"

def recordSystemTime():
    '''
    Record the current time in Epoch notation.
    '''

    return time_ns() // 1000000


def startTraffic(net, sender, receiver, packetCount, experimentStartTime):
    """
    Start a capture in <receiver>, then transmit test packets from <sender>.
    """
    
    # Get the Mininet nodes representing the traffic source and destination
    sender = net.get(sender)
    receiver = net.get(receiver)
    
    # Grab necessary receiver arguments  (where the pcap file is located and what interface to listen for the test traffic)
    receiverInterfaceName = receiver.defaultIntf().name
    pcapFilePath = f"/tmp/traffic_{sender}_{receiver}_{experimentStartTime}.pcapng"

    # Start the receiving end of the communication
    receiverProcess = receiver.popen([
        "sudo",
        "python3", TRAFFIC_GEN, 
        "-r", pcapFilePath, 
        "-e", receiverInterfaceName
    ])

    # give tshark a moment to bind to the interface
    sleep(1)

    # Grab necessary sender arguments (who to send to and out of what interface should the traffic flow out of)
    destinationIPv4Address   = receiver.IP()
    senderIntfName = sender.defaultIntf().name

    # Start the sending end of the communication
    senderProcess = sender.popen([
        "sudo",
        "python3", TRAFFIC_GEN,
        "-s", destinationIPv4Address,
        "-c", str(packetCount),
        "-e", senderIntfName
    ])

    return senderProcess, receiverProcess, pcapFilePath


def stopTraffic(senderProcess, receiverProcess):
    # Wait for the sender to finish naturally
    senderProcess.wait()

    # Ask tshark to stop politely
    receiverProcess.send_signal(signal.SIGINT) # SIGINT (forces it to flush the pcap)

    try:
        receiverProcess.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # If it ignores SIGINT, escalate
        receiverProcess.terminate() # SIGTERM

        try:
            receiverProcess.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # 
            receiverProcess.kill() # SIGKILL
            receiverProcess.wait()


def startReconvergenceExperiment(net, targetNodeName, neighborNodeName, trafficNodes):
    '''
    Fail an interface on a Mininet node connected to a specified neighbor
    to start the reconvergenec experiment.
    '''

    # Get the link between the two nodes
    targetNode = net.get(targetNodeName)
    neighborNode = net.get(neighborNodeName)
    link = net.linksBetween(targetNode, neighborNode)[0]

    # Find the right interface, it's an object within link, link.intf1 or link.intf2
    if link.intf1.node.name == targetNodeName:
        intf_to_disable = link.intf1
        neighbor_intf = link.intf2
    else:
        intf_to_disable = link.intf2
        neighbor_intf = link.intf1

    # Record the experiment start time
    experimentStartTime = recordSystemTime()

    # Start the traffic generation, if specified
    trafficStreams = []
    if(trafficNodes):
        for trafficPair in trafficNodes:
            # Tuple containing (senderProcess, receiverProcess, pcapFilePath)
            trafficStreams.append(startTraffic(net, 
                                                trafficPair[0], trafficPair[1], 
                                                NUM_TEST_PACKETS_TO_SEND, 
                                                experimentStartTime))

    # Disable the interface (the timestamp associated with this event will be logged by the protocol)
    intf_to_disable.ifconfig('down')
    #targetNode.cmd(f"tc qdisc add dev {intf_to_disable.name} root netem loss 100%")

    # Return the status of the interface for confirmation and experiment information
    return not intf_to_disable.isUp(), experimentStartTime, intf_to_disable.name, neighbor_intf.name, trafficStreams


def _mkdirWithPermissions(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    p.chmod(0o777)

    return


def copyLogs(logPattern, dirPath):
    # Convert the search directory and output file to Path objects
    search_dir = Path("/tmp").resolve()
    output_path = Path(dirPath).resolve()    

    # Iterate over all .log files in the source directory.
    for log_file in search_dir.glob(logPattern):
        if log_file.is_file():
            # Construct the destination file path using the same file name.
            destination_file = output_path / log_file.name
            shutil.copy(log_file, destination_file)

            # Update permissions of copied log file
            destination_file.chmod(0o777)

    return


def collectLogs(protocol, topologyName, logDirPath, experimentInfo):
    '''
    Copy protocol log files from a test into a directory to be analyzed.
    '''

    # Information associated with the experiment run
    nodeFailed = experimentInfo[0]
    neighborFailed = experimentInfo[1]
    intfName = experimentInfo[2]
    neighborIntfName = experimentInfo[3]
    experimentStartTime = experimentInfo[4]
    experimentStopTime = experimentInfo[5]
    trafficInExperiment = experimentInfo[6]

    # Generate a name for the experiment instance that was run
    experiment_name = f"{topologyName}_{experimentStartTime}"

    # Create the experiment directory.
    base_dir = Path(logDirPath).resolve() # ~/closnet/logs
    protocol_dir = base_dir / protocol # ~/closnet/logs/<protocol>
    log_dir_path = protocol_dir / experiment_name # ~/closnet/logs/<protocol>/<experiment_name>

    for directory in (base_dir, protocol_dir, log_dir_path):
        _mkdirWithPermissions(directory)

    # Define the subdirectory for protocol (switching node) log files and copy the files into that directory
    nodesDir = log_dir_path / "nodes"
    _mkdirWithPermissions(nodesDir)
    copyLogs(PROTOCOL_LOG_FILE_PATTERN, nodesDir.as_posix())

    # Define the subdirectory for traffic (compute node) log files and copy the files into that directory
    if(trafficInExperiment):
        trafficDir = log_dir_path / "traffic"
        _mkdirWithPermissions(trafficDir)
        copyLogs(TRAFFIC_LOG_FILE_PATTERN, trafficDir.as_posix())

    # Create a log file to record information associated with the experiment run
    experiment_log_file = log_dir_path / "experiment.log"

    failureText = (
        f"Failed node: {nodeFailed}\n"
        f"Interface name: {intfName}\n"
        f"Failed neighbor: {neighborFailed}\n"
        f"Neighbor interface name: {neighborIntfName}\n"
        f"Experiment start time: {experimentStartTime}\n"
        f"Experiment stop time: {experimentStopTime}\n"
        f"Traffic included: {trafficInExperiment}"
    )
    experiment_log_file.write_text(failureText)
    experiment_log_file.chmod(0o777) 

    return str(log_dir_path)


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
    logging.info(f"Convergence time: {experiment.getReconvergenceTime()} milliseconds\n")

    if(experiment.traffic_included):
        logging.info("=== TRAFFIC ===")
        logging.info(experiment.traffic)

    return


def runExperimentAnalysis(logDirPath, experiment: ExperimentAnalysis, debugging=False):
    RESULTS_FILE = "results.log"
    NODE_LOGS_DIR = "nodes"
    TRAFFIC_LOGS_DIR = "traffic"
    
    # Determine the path of where the results log file will be saved to.
    resultsFile = os.path.join(logDirPath, RESULTS_FILE)

    # Open a log file to record results of the analysis.
    logging.basicConfig(
        filename=resultsFile,
        level=logging.DEBUG if debugging else logging.INFO,
        format='%(message)s',
        filemode='w'
    )

    logging.debug("=== DEBUGGING ===")

    # Read through all of the nodes log files to see the reconvergence process (including the failed node as well)
    for logFile, nodeName in experiment.iterLogFiles(NODE_LOGS_DIR, ".log", priorityNodes=(experiment.failed_node, experiment.neighbor_node)):
        logging.debug(f"\n*** Analyzing {nodeName} log file ({logFile}) ***")

        # Through the log records for this node, determine what its total message overhead is and the time of its final update
        nodeConvergenceTime, nodeWasUpdated, nodeOverhead = experiment.parseLogFile(nodeName, logFile)

        # Update CONVERGENCE TIME metric data
        experiment.convergence_times.append(nodeConvergenceTime)

        # Update BLAST RADIUS metric data
        experiment.number_of_nodes += 1
        if(nodeWasUpdated):
            experiment.number_of_updated_nodes += 1

        # Update OVERHEAD metric data
        experiment.overhead += nodeOverhead


    # If there is traffic, read it and analyze it
    if(experiment.traffic_included):
        for logFile, nodes in experiment.iterLogFiles(TRAFFIC_LOGS_DIR, ".pcapng"):
            logging.debug(f"\n*** Analyzing {nodes} traffic log file ({logFile}) ***")
            experiment.traffic = analyzeTraffic(logFile, writeToFile=False)

    # Write the analysis results to the results log file
    writeResults(experiment)

    # Shutdown logging and update permissions
    logging.shutdown()
    Path(resultsFile).chmod(0o777)
