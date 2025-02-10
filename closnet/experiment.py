# Core libraries
import subprocess
from pathlib import Path
import shutil

def failNetworkInterface(net, targetNode, neighborNode):
    '''
    Fail an interface on a Mininet node connected to a specified neighbor.
    '''

    # Get the link between the two nodes
    link = net.linksBetween(net.get(targetNode), net.get(neighborNode))[0]

    # Find the right interface, it's an object within link, link.intf1 or link.intf2
    if link.intf1.node.name == targetNode:
        intf_to_disable = link.intf1
    else:
        intf_to_disable = link.intf2

    # Record the time of failure
    timestamp = subprocess.check_output(['date', '+"%s%3N"'], text=True)

    # Disable the interface
    intf_to_disable.ifconfig('down')

    # Return the status of the interface for confirmation and the time of failure
    return not intf_to_disable.isUp(), timestamp


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


def collectProtocolLogs(dirPath):
    # Convert the search directory and output file to Path objects
    search_dir = Path("/tmp").resolve()
    output_path = Path(dirPath).resolve()    

    # Iterate over all .log files in the source directory.
    for log_file in search_dir.glob("*.log"):
        if log_file.is_file():
            # Construct the destination file path using the same file name.
            destination_file = output_path / log_file.name
            shutil.copy(log_file, destination_file)

    return

def collectLogs(protocol, topologyName, logDirPath, intfFailureTimestamp):
    '''
    Copy protocol log files into a directory for a given experiment run to be analyzed.
    '''

    # Create the experiment directory.
    log_dir_path = Path(logDirPath).resolve() / f"{protocol}" / f"{topologyName}_{intfFailureTimestamp}"
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # Define the two experiment-specific subdirectories
    convergence_dir = log_dir_path / "convergence"
    downtime_dir = log_dir_path / "downtime"

    convergence_dir.mkdir(exist_ok=True)
    downtime_dir.mkdir(exist_ok=True)

    # Copy the protocol log files into the experiment directory
    collectProtocolLogs(convergence_dir.as_posix())

    # Create the interface downtime log file and record the downtime inside of it
    intf_down_file = downtime_dir / "intf_down.log"
    intf_down_file.write_text(f"{intfFailureTimestamp}")

    # Create the node downtime log file and record each node's downtime inside of it
    nodes_down_file = downtime_dir / "nodes_down.log"
    collectMTPNodeDowntimeLogs(nodes_down_file.as_posix())
