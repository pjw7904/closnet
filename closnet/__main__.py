# Core libraries
import json
import os
import subprocess
from sys import exit

# External libraries
import networkx as nx

# Mininet libraries
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel, info

# Custom libraries
from generators.ClosGenerator import ClosGenerator, MTPConfig, BGPDCNConfig
from generators.ClosConfigTopo import ClosConfigTopo

from switches.mtp.mininet_switch.MTPSwitch import MTPSwitch, MTPHost
from switches.bgp.mininet_switch.BGPSwitch import BGPSwitch, BGPHost

from ConfigParser import *
from NodeConfigGenerator import *

# Constants
CLOS_TOPOS_DIR = os.path.join(os.path.dirname(__file__), "topologies/clos")
GRAPHML_TOPOS_DIR = os.path.join(os.path.dirname(__file__), "topologies/graphml")
MTP = "mtp"
BGP = "bgp"


def loadTopologyConfig(topologyName: str) -> nx.graph:
    '''
    Load a JSON-formatted configuration file for the topology.

    :param topologyName: The name for the topology.
    :returns: The topology configuration as a NetworkX graph.
    '''

    topologyConfig = None

    # Loop through all files in the topologies/clos directory to attempt to find a match.
    for testName in os.listdir(CLOS_TOPOS_DIR):
        if(testName.startswith(topologyName)):
            with open(os.path.join(CLOS_TOPOS_DIR, testName)) as configFile:
                topologyConfig = nx.node_link_graph(json.load(configFile))
                break

    return topologyConfig


def saveTopologyConfig(topologyName: str, topology: ClosGenerator) -> nx.graph:
    '''
    Save a JSON-formatted configuration file for the topology.

    :param topologyName: The name for the topology.
    :param topology: The topology configuration.
    :returns: The topology configuration as a NetworkX graph.
    '''

    topologyConfig = nx.node_link_data(topology.clos)

    fileName = f"{topologyName}.json"
    with open(os.path.join(CLOS_TOPOS_DIR, fileName), mode="w") as configFile:
        json.dump(topologyConfig, configFile)

    return nx.node_link_graph(topologyConfig)


def generateTopology(closConfigGenerator, config, topologyName, portDensityModifications):
    # Define the Clos topology parameters
    topology = closConfigGenerator(config.ports,
                                   config.tiers,
                                   southboundPortsConfig=portDensityModifications)

    # Build the Clos topology
    topology.buildGraph()

    # Save the topology configuration
    topology = saveTopologyConfig(topologyName, topology)

    return topology


def main():
    '''
    Entry into the program. Design a folded-Clos topology and pick a protocol to install on it.
    '''

    # Set the logging level
    setLogLevel('info')

    # Grab command-line arguments to build the topology
    config = parseArgs()

    # Validate the folded-Clos configuration and determine if this topology already has been saved.
    topologyStatus = validateTopology(config)
    validTopology = topologyStatus[0] # valid = True, not valid = False
    topologyMessage = topologyStatus[1] # prints out a message for the user

    # If the topology designed is not a valid folded-Clos topology, end the program
    print(topologyMessage)
    if(not validTopology):
        exit(0)

    # Remove any lingering log files so that it doesn't screw up incoming log files.
    clearNodeConfigFiles()

    # Configure the custom southbound port density ranges if necessary
    if(config.southbound):
        portDensityModifications = {tier[0]: tier[1] for tier in config.southbound}
    else:
        portDensityModifications = None

    # Generate the name associated with this particular topology.
    topologyName = generateTestName(config)
    print(f"Topology name = {topologyName}")

    # Determine if this topology already has a configuration.
    topology = loadTopologyConfig(topologyName)

    # If this topology does not already have pre-computed configuration, build it.
    if(not topology):
        if(config.protocol == MTP):
            topology = generateTopology(MTPConfig,
                                        config, topologyName, portDensityModifications)

        elif(config.protocol == BGP):
            topology = generateTopology(BGPDCNConfig,
                                        config, topologyName, portDensityModifications)
        else:
            print("Protocol chosen unknown.")
            os.exit(1)
    else:
        print("topology exists!")

    # Generate the configuration files for each node in the topology.
    if(config.protocol == MTP):
        generateConfigMTP(topology)
        protocolSwitch = MTPSwitch
        protocolHost = MTPHost

    elif(config.protocol == BGP):
        generateConfigBGP(topology)
        protocolSwitch = BGPSwitch
        protocolHost = BGPHost

    mininetTopology = ClosConfigTopo(topology)

    # Define the Mininet
    net = Mininet(topo=mininetTopology, 
                  switch=protocolSwitch,
                  host=protocolHost,
                  controller=None,
                  build=False)

    # Build the Mininet
    net.build()

    # Start nodes in the folded-Clos from tiers N to 0
    for tier in sorted(mininetTopology.nodesByTier.keys(), reverse=True):
        nodesInCurrentTier = mininetTopology.nodesByTier[tier]
        info(f"\n*** Starting switches in tier {tier}:\n")

        for node in nodesInCurrentTier:
            net[node].start([]) # empty controller list argument is required, even though we don't use controllers

    # Start the interactive Mininet terminal
    CLI(net)

    # Shut down all nodes and tear down the Mininet
    net.stop()

    return


if __name__ == "__main__":
    main()
