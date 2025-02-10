# Core libraries
import subprocess

def failNetworkInterface(net, targetNode, neighborNode):
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