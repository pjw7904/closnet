# Core libraries
import subprocess
from pathlib import Path
import shutil


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


def collectMTPNodeDowntimeLogs(dirPath):
    # Convert the search directory and output file to Path objects
    search_dir = Path("/tmp").resolve()
    output_path = Path(dirPath).resolve()

    # List to store the formatted lines
    formatted_lines = []
    
    # Search for all files with the '.down' extension in the directory (recursively)
    for file_path in search_dir.rglob("*.down"):
        if file_path.is_file():
            # Extract the node name from the file name (stem removes the extension)
            node = file_path.stem

            try:
                # Read the file's content and split into lines
                lines = file_path.read_text().splitlines()

                if lines:  # Ensure the file isn't empty
                    first_line = lines[0]
                    # Format the output as <node>:<first_line>
                    formatted_lines.append(f"{node}:{first_line}")

                else:
                    print(f"Warning: {file_path} is empty.")
            
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    # Ensure the parent directory of the output file exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write all formatted lines to the output file, one per line
    output_path.write_text("\n".join(formatted_lines) + "\n")

    return


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
