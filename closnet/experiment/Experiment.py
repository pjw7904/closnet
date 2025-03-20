# Core libraries
import subprocess
import shutil
import logging
import os
from pathlib import Path


# Custom libraries
from closnet.experiment.ExperimentAnalysis import ExperimentAnalysis

def recordSystemTime():
    '''
    Record the current time in Epoch notation.
    '''

    return subprocess.check_output(["date", "+%s%3N"], text=True).strip() # Output comes with newline, so strip it.


def startReconvergenceExperiment(net, targetNode, neighborNode):
    '''
    Fail an interface on a Mininet node connected to a specified neighbor
    to start the reconvergenec experiment.
    '''

    # Get the link between the two nodes
    link = net.linksBetween(net.get(targetNode), net.get(neighborNode))[0]

    # Find the right interface, it's an object within link, link.intf1 or link.intf2
    if link.intf1.node.name == targetNode:
        intf_to_disable = link.intf1
        neighbor_intf = link.intf2
    else:
        intf_to_disable = link.intf2
        neighbor_intf = link.intf1

    # Record the experiment start time
    experimentStartTime = recordSystemTime()

    # Disable the interface (the timestamp associated with this event will be logged by the protocol)
    intf_to_disable.ifconfig('down')

    # Return the status of the interface for confirmation and experiment information
    return not intf_to_disable.isUp(), experimentStartTime, intf_to_disable.name, neighbor_intf.name


def copyProtocolLogs(dirPath):
    # Convert the search directory and output file to Path objects
    search_dir = Path("/tmp").resolve()
    output_path = Path(dirPath).resolve()    

    # Iterate over all .log files in the source directory.
    for log_file in search_dir.glob("*.log"):
        if log_file.is_file():
            # Construct the destination file path using the same file name.
            destination_file = output_path / log_file.name
            shutil.copy(log_file, destination_file)

            # Update permissions of copied log file
            destination_file.chmod(0o644)

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

    # Generate a name for the experiment instance that was run
    experiment_name = f"{topologyName}_{experimentStartTime}"

    # Create the experiment directory.
    log_dir_path = Path(logDirPath).resolve() / f"{protocol}" / experiment_name
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # Define the subdirectory for node log files
    nodes_dir = log_dir_path / "nodes"
    nodes_dir.mkdir(exist_ok=True)

    # Copy the protocol log files into the experiment directory
    copyProtocolLogs(nodes_dir.as_posix())

    # Create a log file to record information associated with the experiment run
    experiment_log_file = log_dir_path / "experiment.log"

    failureText = (
        f"Failed node: {nodeFailed}\n"
        f"Interface name: {intfName}\n"
        f"Failed neighbor: {neighborFailed}\n"
        f"Neighbor interface name: {neighborIntfName}\n"
        f"Experiment start time: {experimentStartTime}\n"
        f"Experiment stop time: {experimentStopTime}"
    )
    experiment_log_file.write_text(failureText)

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
    logging.info(f"Convergence time: {experiment.getReconvergenceTime()} milliseconds")

    return


def runExperimentAnalysis(logDirPath, experiment: ExperimentAnalysis, debugging=False):
    RESULTS_FILE = "results.log"
    NODE_LOGS_DIR = "nodes"
    
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
    for logFile, nodeName in experiment.iterLogFiles(NODE_LOGS_DIR):
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

    # Write the analysis results to the results log file
    writeResults(experiment)
