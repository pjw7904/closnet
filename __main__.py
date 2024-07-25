# Core libraries
import json
import os
import argparse
from sys import exit

# External libraries
import networkx as nx

# Mininet libraries
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI

# Custom libraries
from generators.ClosGenerator import ClosGenerator, MTPConfig
from ConfigParser import *

# Constants
CLOS_TOPOS_DIR = os.path.join(os.path.dirname(__file__), "topologies/clos")
GRAPHML_TOPOS_DIR = os.path.join(os.path.dirname(__file__), "topologies/graphml")


def loadTopologyConfig(topologyName: str) -> nx.graph:
    '''
    load a JSON-formatted configuration file for the topology.

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

    return topologyConfig


def main():
    '''
    Entry into the program. Design a folded-Clos topology and pick a protocol to install on it.
    '''

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

    # Generate the name associated with this particular topology
    topologyName = generateTestName(config)
    print(f"Topology name = {topologyName}")

    # Determine if this topology already has a configuration
    topology = loadTopologyConfig(topologyName)

    # Build the topology configuration based on the protocol chosen if the config is new.
    if(not topology):
        topology = MTPConfig(config.ports, config.tiers)
        topology.buildGraph()
        topology = saveTopologyConfig(topologyName, topology) # Save the topology configuration
    else:
        print("topology exists!")


if __name__ == "__main__":
    main()
