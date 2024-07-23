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
from generators.ClosGenerator import MTPConfig
from ConfigParser import *


def main():
    '''
    Entry into the program, allows you to pick a protocol and topology to run.
    '''

    CLOS_TOPOS_DIR = "topologies/clos"
    GRAPHML_TOPOS_DIR = "topologies/graphml"
    
    # Validate the folded-Clos configuration and determine if this topology already has been saved.
    configArguments = parseArgs()

    topologyStatus = validateTopology(configArguments)
    validTopology = topologyStatus[0]
    topologyMessage = topologyStatus[1]

    print(topologyMessage)
    if(not validTopology):
        exit(0)

    topologyName = generateTestName(configArguments)
    print(topologyName)

    # Build the topology based on the protocol chosen.
    #topology = MTPConfig(4,3)
    #topology.buildGraph()
    # os.path.dirname(__file__)
    #data = nx.node_link_data(topology.clos, name="node")
    #with open(f'{os.getcwd()}/MTP-Mininet/test.json', "w") as outfile:
    #    json.dump(data, outfile)


if __name__ == "__main__":
    main()
