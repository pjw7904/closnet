# Core libraries
import json
import os
from sys import exit
from time import sleep

# External libraries
import networkx as nx

# Mininet libraries
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.clean import cleanup

# Custom libraries
from closnet.ClosGenerator import ClosGenerator
from closnet.topo_definitions.ClosConfigTopo import ClosConfigTopo
from closnet.experiment.Experiment import *
from closnet.experiment.ExperimentAnalysis import ExperimentAnalysis
from closnet.ConfigParser import *
from closnet.NodeConfigGenerator import *
from closnet.utils.DrawClos import drawFoldedClos
from closnet.utils.GenerateCSV import run as gen_csv

## Meshed Tree Protocol (MTP) modules
from closnet.protocols.mtp.mininet_switch.MTPSwitch import MTPSwitch, MTPHost
from closnet.protocols.mtp.config.MTPClosConfig import MTPClosConfig
from closnet.protocols.mtp.analysis.MTPAnalysis import MTPAnalysis

## Border Gateway Protocol (BGP) modules
from closnet.protocols.bgp.mininet_switch.BGPSwitch import BGPSwitch, BGPHost
from closnet.protocols.bgp.config.BGPClosConfig import BGPClosConfig
from closnet.protocols.bgp.analysis.BGPAnalysis import BGPAnalysis

# Constants
CLOS_TOPOS_DIR = os.path.join(os.path.dirname(__file__), "topologies/clos")
MTP = "mtp"
BGP = "bgp"


def stopNetAndCleanup() -> None:
    cleanup()
    exit(0)


def startInteractiveMode(net) -> None:
    info(f"\n*** Starting interactive mode:\n")
    CLI(net)

    # Shut down all nodes and tear down the Mininet
    net.stop()

    return


def startExperimentMode(net, config, topologyName) -> None:
    info(f"\n*** Starting experiment mode:\n")

    info(f"EXPERIMENT STEP 0: Collect experiment information.\n")

    # Determine the type of failure (hard or soft link failure) this experiment requires
    failureType = ExperimentAnalysis.SOFT_LINK_FAILURE if config.soft_failure else ExperimentAnalysis.HARD_LINK_FAILURE
    info(f"\tFailure Type: {'Soft link failure' if config.soft_failure else 'Hard link failure'}\n")

    # Collect IP addressing for nodes attached to the failed link for analysis later (if necessary)
    addressingDict = collectLinkAddressing(net, config.node_to_fail, config.neighbor_of_failing_node)
    info(f"\tAddressing map created with {len(addressingDict)} entries\n")

    # Collect any client nodes are sending traffic during the experiment
    trafficRequests = collectTrafficRequests(config.traffic)
    trafficType = "ping" if bool(config.traffic["use_ping"]) is True else "custom traffic generator"
    info(f"\t{len(trafficRequests)} pairs of clients sending traffic using {trafficType}\n")

    # Give the topology time for initial convergence
    timeToSleep = config.tiers * 4
    info(f"EXPERIMENT STEP 1: Giving the nodes {timeToSleep} seconds to get converged...\n")

    sleep(timeToSleep)

    # Start the reconvergence experiment by failing the specified interface and confirm the operation was successful
    (
        interfaceFailureConfirmation,
        experimentStartTime,
        intfName,
        neighborIntfName,
        trafficStreams,
    ) = startReconvergenceExperiment(
        net,
        config.node_to_fail, config.neighbor_of_failing_node, config.soft_failure,
        trafficRequests,
    )

    if(not interfaceFailureConfirmation):
        info(f"EXPERIMENT STEP 2: Interface failure was not successful.\n")

        stopNetAndCleanup()
    else:
        info(f"EXPERIMENT STEP 2: The interface on {config.node_to_fail} was failed connected to {config.neighbor_of_failing_node}.\n")

        # For a soft link failure, the interface starvation (failure) time needs to be pre-added to the analysis class, as there isn't a log generated for it, only the failure detection.
        timeOfFailure = interfaceFailureConfirmation if config.soft_failure else None

        # For a soft link failure, the interface starvation (failure) time needs to be pre-added to the analysis class, 
        # as there isn't a log generated for it, only the failure detection.
        if(config.soft_failure):
            timeOfFailure = interfaceFailureConfirmation
            failureUsesBFD = config.bfd if config.protocol == BGP else False # In the event MTP and bfd = True is accidently set
        else:
            timeOfFailure = None
            failureUsesBFD = False

    # Give the topology time for reconvergence after the the interface failure
    info(f"EXPERIMENT STEP 3: Giving the nodes {timeToSleep} seconds to get reconverged...\n")

    sleep(timeToSleep)

    # Notify user experiment is being torn down.
    info(f"EXPERIMENT STEP 4: Experiment is complete, tearing down topology. \n")

    experimentStopTime = recordSystemTime()

    info(f"\tStopping traffic streams...")

    trafficInExperiment = False
    for trafficStream in trafficStreams:
        senderProcess = trafficStream[0]
        receiverProcess = trafficStream[1]
        stopTraffic(senderProcess, receiverProcess)
        trafficInExperiment = True

    info(f"\tStopping switches and clients...")

    net.stop()

    # Collect log files generated
    info("EXPERIMENT STEP 5: Collect log files generated by experiment.\n")

    experimentInfo = (config.node_to_fail, config.neighbor_of_failing_node, 
                        intfName, neighborIntfName, 
                        experimentStartTime, experimentStopTime, 
                        trafficInExperiment, 
                        failureType, timeOfFailure, failureUsesBFD
                    )
    experimentDirPath = collectLogs(config.protocol, topologyName, config.log_dir_path, addressingDict, experimentInfo)
    
    info(f"\tExperiment directory: {experimentDirPath}\n")

    info("EXPERIMENT STEP 6: Run experiment analysis and record results.\n")

    if(config.protocol == MTP):
        experiment = MTPAnalysis(experimentDirPath)
    elif(config.protocol == BGP):
        experiment = BGPAnalysis(experimentDirPath)
    else:
        raise Exception("Unknown/no protocol chosen, experiment cannot be analyzed")

    runExperimentAnalysis(experimentDirPath, experiment, config.debugging)

    return


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
    validTopology, topologyMessage = validateTopology(config)
    print(topologyMessage)

    # If the topology designed is not a valid folded-Clos topology, end the program
    if(not validTopology):
        stopNetAndCleanup()

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

    # Aggregate results in a CSV file and exit if desired. 
    if config.csv:
        gen_csv(config.protocol, topologyName)
        stopNetAndCleanup()

    # Determine if this topology already has a configuration.
    topology = loadTopologyConfig(topologyName)

    # If this topology does not already have pre-computed configuration, build it.
    if(not topology):
        if(config.protocol == MTP):
            topology = generateTopology(MTPClosConfig,
                                        config, topologyName, portDensityModifications)

        elif(config.protocol == BGP):
            topology = generateTopology(BGPClosConfig,
                                        config, topologyName, portDensityModifications)
        else:
            print("Protocol chosen unknown.")
            stopNetAndCleanup()
    else:
        print("topology exists!")


    # If the topology configuration was built, but you only want a figure of the topology, exit here.
    if(config.visualize):
        info("No Mininet built, JSON topology file saved and figure should appear.\n")
        
        # Users that want to visualize an experiment and how the topology is impacted can do so.
        if(config.file):
            drawFoldedClos(topology, 
                           failed_link=(config.node_to_fail, config.neighbor_of_failing_node),
                           show_pristine=False)
        
        # Otherwise, if the user just wants a picture of the folded-Clos, use CLI options like you would in interactive mode 
        else:
            drawFoldedClos(topology)

        stopNetAndCleanup()

    # Generate the configuration files for each node in the topology.
    if(config.protocol == MTP):
        generateConfigMTP(topology)
        protocolSwitch = MTPSwitch
        protocolHost = MTPHost

    elif(config.protocol == BGP):
        BGPSwitch.ENABLE_BFD = config.bfd
        generateConfigBGP(topology, config.bfd)
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

    # Start network testing in one of the two available modes (interactive or experiment) 
    if(config.file):
        startExperimentMode(net, config, topologyName)
    else:
        startInteractiveMode(net)

    return


if __name__ == "__main__":
    main()
