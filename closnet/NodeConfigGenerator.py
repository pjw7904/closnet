# Core libraries
import os
from pathlib import Path

# External libraries
from mako.template import Template

# Constants
COMPUTE_TIER = 0 # No control protocol configuration for the compute nodes.
CONFIG_DIR = "/tmp" # Place all node config files in the tmp directory.
CONFIG_EXTENSIONS = {".conf", ".log", ".stdout", ".down", ".pid"} # All generated node config files contain a subset of these file extensions

def generateConfigMTP(topology):
    '''
    Create and save configuration files for MTP nodes.

    :param topology: The NetworkX-formatted topology.
    '''

    TEMPLATE_LOCATION = os.path.join(os.path.dirname(__file__), 
                                     "switches/mtp/config_template/mtp_conf.mako")

    # Open the MTP configuration template
    try: 
        mtpTemplate = Template(filename=TEMPLATE_LOCATION)
    except Exception as e:
        print(f"Exception: {e}")

    # Iterate through the nodes in the topology
    for node in topology:
        tier = topology.nodes[node]['tier']

        # Only configure MTP devices, not compute devices.
        if(tier > COMPUTE_TIER):
            # Grab configuration data
            nodeTemplate = {'tier': tier, 
                            'isTopSpine': topology.nodes[node]['isTopTier']}

            # Process the data and render a custom MTP configuration.
            mtpConfig = mtpTemplate.render(**nodeTemplate)

            # Save the configuration in the file <node_name>.conf
            with open(os.path.join(CONFIG_DIR, f"{node}.conf"), 'w') as configFile:
                configFile.write(mtpConfig)

    return


def generateConfigBGP(topology):
    '''
    Create and save configuration files for BGP nodes.

    :param topology: The NetworkX-formatted topology.
    '''

    TEMPLATE_LOCATION = os.path.join(os.path.dirname(__file__), 
                                     "switches/bgp/config_template/bgp_conf.mako")

    # Open the BGP configuration template
    try: 
        bgpTemplate = Template(filename=TEMPLATE_LOCATION)
    except Exception as e:
        print(f"Exception: {e}")

    # Iterate through the nodes in the topology
    for node in topology:
        # Store information about BGP-speaking neighbors to configure neighborship
        neighboringNodes = []

        if(topology.nodes[node]['tier'] > COMPUTE_TIER):
            
            # Find the node's BGP-speaking neighbors and determine their ASN as well as their IPv4 address used on the subnet shared by the nodes.
            for neighbor, _ in topology.nodes[node]['ipv4'].items():
                if(topology.nodes[neighbor]['tier'] > COMPUTE_TIER):
                    neighboringNodes.append({'asn':topology.nodes[neighbor]['ASN'], 
                                            'ip':topology.nodes[neighbor]['ipv4'][node]})

            # In addition to storing neighbor information, store any compute subnets that the node must advertise to neighbors (leaf's only).
            nodeTemplate = {'node_name': node,
                            'neighbors': neighboringNodes, 
                            'bgp_asn': topology.nodes[node]['ASN'], 
                            'networks': topology.nodes[node]['advertise']}

            # Process the data and render a custom BGP configuration.
            bgpConfig = bgpTemplate.render(**nodeTemplate)

            # Save the configuration in the file <node_name>.conf
            with open(os.path.join(CONFIG_DIR, f"{node}.conf"), 'w') as configFile:
                configFile.write(bgpConfig)

    return

def clearNodeConfigFiles() -> None:
    '''
    Delete data from prior Closnet runs.
    '''

    configDir = Path(CONFIG_DIR)

    for file in configDir.iterdir():
        if file.suffix in CONFIG_EXTENSIONS:
            try:
                file.unlink()

            except FileNotFoundError:
                print(f"Issue deleting file {file.name}")

    return
