"""
Author: Peter Willis
Desc: Class to help build Clos topologies and the node attributes required.
"""

# Core libraries
from copy import deepcopy
from ipaddress import IPv4Network
from collections import defaultdict

# External libraries
import networkx as nx

class ClosGenerator:
    # Vertex prefixes to denote position in topology (TOF = Top of Fabric).
    TOF_NAME = "T"
    SPINE_NAME = "S"
    LEAF_NAME = "L"
    COMPUTE_NAME = "C"

    # Specific tier values.
    LOWEST_SPINE_TIER = 2
    LEAF_TIER = 1
    COMPUTE_TIER = 0

    # To be filled in by subclasses built for a specific network protocol.
    PROTOCOL = None

    def __init__(self, k, t, southboundPortsConfig=None):
        """
        Initializes a graph and its data structures to hold network information.

        :param k: Degree shared by each node.
        :param t: Number of tiers in the graph.
        :param southboundPortsConfig: Custom override for the number of southbound interfaces for devices at a given set of tiers
        """

        self.clos = nx.Graph(topTier=t)
        
        self.sharedDegree = k
        self.numTiers = t

        # Check to make sure the input is valid, return an error if not
        if(self.isNotValidClosInput()):
            raise ValueError("Invalid Clos input (must be equal number of north and south links)")

        # Set up the number of southbound ports, either the default, a user provided dictonary, or a combination of both.
        self.southboundPorts = defaultdict(lambda: k//2)
        self.southboundPorts[t] = k # The top-tier has all of its ports southbound.

        if(southboundPortsConfig):
            self.setSouthboundPorts(southboundPortsConfig)

    def isNotValidClosInput(self):
        """
        Checks if the shared degree inputted is an even number and that the number of tiers is at least 2. This confirms that the folded-Clos will have a 1:1 oversubscription ratio.

        :returns: True or false depending on the shared degree and number of tiers value.
        """

        if(self.sharedDegree % 2 != 0 and self.numTiers < 2):
            return True
        else:
            return False

    def setSouthboundPorts(self, customPorts):
        """
        Set a custom number of southbound ports for specific tiers. 

        :param customPorts: A dictionary mapping tier numbers to the desired number of southbound ports.
        """
        for tier, ports in customPorts.items():
            self.southboundPorts[tier] = ports

        return

    def getNodeTitle(self, currentTier, topTier):
        """
        Determine the type of node and give it the name associated with that type. This name is the start of the full node name.

        :param currentTier: The folded-Clos tier that is being anaylzed currently.
        :param topTier: The folded-Clos tier at the top of the topology.
        :returns: The type given to the node.
        """

        if(currentTier == topTier):
            title = self.TOF_NAME    
        elif(currentTier > self.LEAF_TIER):
            title = self.SPINE_NAME
        elif(currentTier == self.LEAF_TIER):
            title = self.LEAF_NAME
        elif(currentTier == self.COMPUTE_TIER):
            title = self.COMPUTE_NAME
        else:
            title = ""

        return title
       
    def generateNode(self, prefix, nodeNum, currentTier, topTier):
        """
        Determine what a given node should be named and create it. The format of a name is node_title-pod_prefix-num for all nodes minus the top tier, which do not use a pod_prefix.

        :param prefix: The prefix for a given tier within a pod in the topology.
        :param nodeNum: A number associated with that specific node.
        :param currentTier: The folded-Clos tier that is being anaylzed currently.
        :param topTier: The folded-Clos tier at the top of the topology.

        :returns: The name given to the node.
        """

        title = self.getNodeTitle(currentTier, topTier)

        if(currentTier != topTier):
            name = f"{title}{currentTier}_{prefix}{nodeNum}"
        else:
            name = f"{title}{currentTier}_{nodeNum}"

        return name

    def generatePrefix(self, prefix, addition):
        """
        Generate the prefix for a given tier within a pod in the topology.
        
        :param prefix: The starting prefix to modify.
        :param addition: Additional value to add to the starting prefix to create a new prefix.

        :returns: The new prefix.
        """

        return prefix + addition

    def determinePrefixVisitedStatus(self, prefix, prefixList):
        """
        Determine if the prefix has been visited in the BFS algorithm yet. If it has not, add it to be visited.
        
        :param prefix: The prefix for a given tier within a pod in the topology.
        :param prefixList: The list of visited prefixes (tiers within a pod).
        """

        if(prefix not in prefixList):
            prefixList.append(prefix)

        return

    
    def connectNodes(self, northNode, southNode, northTier, southTier):
        """
        Connect two nodes together via an edge. The nodes must be in adjacent tiers (ex: tier 2 and tier 3). The nodes also understand if their new neighbor is above them (northbound) or below them (southbound). Subclasses specific to a protocol should override this method with its specific attribute needs beyond north-south interconnection. This base method is provided to simply view the output of a given folded-Clos topology.

        :param northNode: The node in tier N.
        :param southNode: The node in tier N-1.
        :param northTier: The tier value N.
        :param southTier: The tier value N-1.
        """
        
        # Only add the nodes to the topology if they haven't already been added prior.
        if(northNode not in self.clos):
            self.clos.add_node(northNode, northbound=[], southbound=[], tier=northTier)
        if(southNode not in self.clos):
            self.clos.add_node(southNode, northbound=[], southbound=[], tier=southTier)
        
        # Note that they are connected to each other in the appropriate direction.
        self.clos.nodes[northNode]["southbound"].append(southNode)
        self.clos.nodes[southNode]["northbound"].append(northNode)
        
        # Add the edge between the two nodes to the topology
        self.clos.add_edge(northNode, southNode)

        return

    def buildGraph(self):
        """
        Build a folded-Clos with t tiers and each node containing k interfaces. It is built using a modified BFS algorithm, 
        starting with the top tier of the spines and working its way down to the leaf nodes and compute nodes.
        """

        k = self.sharedDegree
        t = self.numTiers

        currentTierPrefix = [""] # Queue for current prefix being connected to a southern prefix
        nextTierPrefix = [] # Queue for the prefixes of the tier directly south of the current tier

        currentPodNodes = (k//2)**(t-1) # Number of top-tier nodes to start, but will shrink at lower tiers
        topTier = t # The starting tier, and the highest tier in the topology
        currentTier = t # Tracking the tiers as it iterates down them

        while currentTierPrefix:
            currentPrefix = currentTierPrefix.pop(0)

            nodeNum = 0 # The number associated with a given node, appended after the prefix (ex: 1-1-1, pod 1-1, node number 1)

            for node in range(1,currentPodNodes+1):
                # Determine the name of the current node at the current tier
                northNode = self.generateNode(currentPrefix, str(node), currentTier, topTier)

                # Get the number of southbound ports for this tier and add 1 because range is exclusive.
                portRange = self.southboundPorts[currentTier] + 1

                for intf in range(1, portRange):
                    # Per BFS logic, mark the neighbor as visited if it has not already and add it to the queue.

                    # All tiers > 2.
                    if(currentTier > self.LOWEST_SPINE_TIER):
                        southPrefix = self.generatePrefix(currentPrefix, str(intf))
                        self.determinePrefixVisitedStatus(southPrefix, nextTierPrefix)
                        southNodeNum = (nodeNum%(currentPodNodes // (k//2)))+1

                    # The Leaf tier needs to have the same prefix of the spine tier (tier-2), as that is the smallest unit (pod).
                    elif(currentTier == self.LOWEST_SPINE_TIER):
                        southPrefix = currentPrefix
                        self.determinePrefixVisitedStatus(southPrefix, nextTierPrefix)
                        southNodeNum = intf

                    # Tier 1 connects to Tier 0, the compute nodes.
                    elif(currentTier == self.LEAF_TIER):
                        southPrefix = northNode.split('_', 1)[1]
                        southNodeNum = intf

                    southNode = self.generateNode(southPrefix, str(southNodeNum), currentTier-1, topTier)

                    self.connectNodes(northNode, southNode, currentTier, currentTier-1)

                nodeNum += 1

            if(not currentTierPrefix):
                currentTierPrefix = deepcopy(nextTierPrefix)
                nextTierPrefix.clear()

                # Proper distribution of links for 2-tier topologies
                if(currentTier == topTier and topTier == self.LOWEST_SPINE_TIER):
                    currentPodNodes = k

                # The number of connections in the next tier below will be cut down appropriately
                if(currentTier > self.LOWEST_SPINE_TIER):
                    currentPodNodes = currentPodNodes // (k//2)

                currentTier -= 1 # Now that the current tier is complete, move down to the next one
        return
                
    def getClosStats(self):
        """
        Compute stats about the folded-Clos topology built.
        
        :returns: A string containing a number of facts about the folded-Clos topology.
        """

        numTofNodes = (self.sharedDegree//2)**(self.numTiers-1)
        numServers = 2*((self.sharedDegree//2)**self.numTiers)
        numSwitches = ((2*self.numTiers)-1)*((self.sharedDegree//2)**(self.numTiers-1))
        numLeaves = 2*((self.sharedDegree//2)**(self.numTiers-1))
        
        if(self.numTiers == 2):
            numPods = 1
        else:
            numPods = 2*((self.sharedDegree//2)**(self.numTiers-2))

        stats = f"Number of ToF Nodes: {numTofNodes}\nNumber of physical servers: {numServers}\nNumber of networking nodes: {numSwitches}\nNumber of leaves: {numLeaves}\nNumber of Pods: {numPods}\n"
        
        return stats
    
    def getNetworks(self):
        """
        Return the edges of the network.
        
        :returns: The edges of the network.
        """
   
        return self.clos.edges

    def getNodes(self):
        """
        Return the nodes of the network.
        
        :returns: The nodes of the network.
        """
        
        return self.clos.nodes

    def iterNodes(self, noComputeNodes=False):
        for node in self.getNodes():
            if(noComputeNodes and not self.isNetworkNode(node)):
                continue
            else:
                yield node

    def isNetworkNode(self, node):
        return self.clos.nodes[node]["tier"] > self.COMPUTE_TIER
    
    def getNodeAttribute(self, node, attribute, subattribute=None):
        return self.clos.nodes[node][attribute] if subattribute is None else self.clos.nodes[node][attribute][subattribute]

    def logGraphInfo(self):
        """
        Output folded-Clos topology information into a log file.
        """
        
        k = self.sharedDegree
        t = self.numTiers
        topTier = t

        numTofNodes = (k//2)**(t-1)
        numServers = 2*((k//2)**t)
        numSwitches = ((2*t)-1)*((k//2)**(t-1))
        numLeaves = 2*((k//2)**(t-1))
        numPods = 2*((k//2)**(t-2))
        
        with open(f'clos_k{self.sharedDegree}_t{self.numTiers}.log', 'w') as logFile:
            logFile.write("=============\nFOLDED CLOS\nk = {k}, t = {t}\n{k}-port devices with {t} tiers.\n=============\n".format(k=k, t=t))

            logFile.write("Number of ToF Nodes: {}\n".format(numTofNodes))
            logFile.write("Number of physical servers: {}\n".format(numServers))
            logFile.write("Number of networking nodes: {}\n".format(numSwitches))
            logFile.write("Number of leaves: {}\n".format(numLeaves))
            logFile.write("Number of Pods: {}\n".format(numPods))

            for tier in reversed(range(topTier+1)):
                nodes = [v for v in self.clos if self.clos.nodes[v]["tier"] == tier]
                logFile.write("\n== TIER {} ==\n".format(tier))

                for node in sorted(nodes):
                    logFile.write(node)
                    logFile.write("\n\tnorthbound:\n")
                    
                    for n in self.clos.nodes[node]["northbound"]:
                        logFile.write("\t\t{}\n".format(n))
                        
                    logFile.write("\n\tsouthbound:\n")
                    
                    for s in self.clos.nodes[node]["southbound"]:
                        logFile.write("\t\t{}\n".format(s))
                        
        return

    def jsonGraphInfo(self):
        '''
        Get a JSON-formatted output of the graph information
        
        :returns: JSON object containing the folded-Clos configuration.
        '''

        jsonData = {"sharedDegree": self.sharedDegree, 
                    "numTiers": self.numTiers,
                    "protocol": self.PROTOCOL}

        for tier in reversed(range(self.numTiers+1)):
            nodes = [v for v in self.clos if self.clos.nodes[v]["tier"] == tier]
            jsonData[f"tier_{tier}"] = {}

            for node in sorted(nodes):
                jsonData[f"tier_{tier}"][node] = {"northbound": [], "southbound": []}

                for northNode in self.clos.nodes[node]["northbound"]:
                    jsonData[f"tier_{tier}"][node]["northbound"].append(northNode)

                for southNode in self.clos.nodes[node]["southbound"]:
                    jsonData[f"tier_{tier}"][node]["southbound"].append(southNode)


        return jsonData

    def saveAsGraphml(self):
        SMALL_PADDING = " " * 2
        LARGE_PADDING = " " * 4
        
        with open(f'clos_k{self.sharedDegree}_t{self.numTiers}.graphml', 'w') as graphmlFile:
            graphmlFile.write("<?xml version='1.0' encoding='utf-8'?>\n")
            graphmlFile.write('<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">\n')
            graphmlFile.write(f'{SMALL_PADDING}<graph edgedefault="undirected">\n')
            
            # Fill in the nodes first
            for node in self.getNodes():
                graphmlFile.write(f'{LARGE_PADDING}<node id="{node}" />\n'.rjust(4))

            # Then the edges
            for node in self.getNetworks():
                graphmlFile.write(f'{LARGE_PADDING}<edge source="{node[0]}" target="{node[1]}" />\n')
                
            graphmlFile.write(f"{SMALL_PADDING}</graph>\n</graphml>")
        
        return