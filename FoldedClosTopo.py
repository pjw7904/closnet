'''
author: Peter Willis (pjw7904@rit.edu)

A custom topology that can be used to build folded-Clos topologies for data center network testing.
'''

from mininet.topo import Topo
from mininet.log import info
from copy import deepcopy

class FoldedClosTopo(Topo):
    '''
    Building a folded-Clos topology for Mininet testing.
    '''

    # Vertex prefixes to denote position in topology
    TOF_NAME = "T"
    SPINE_NAME = "S"
    LEAF_NAME = "L"
    COMPUTE_NAME = "C"

    # Specific tier values
    LOWEST_SPINE_TIER = 2
    LEAF_TIER = 1
    COMPUTE_TIER = 0

    def build(self, k, t):
        '''
        k = Degree shared by each node
        t = Number of tiers in the graph
        '''

        if(self.isNotValidClosInput(k)):
            raise Exception("Invalid Clos input (must be equal number of north and south links)")
        
        # To keep track of nodes that have been added.
        self.addedNodes = {}
        
        currentTierPrefix = [""] # Queue for current prefix being connected to a southern prefix
        nextTierPrefix = [] # Queue for the prefixes of the tier directly south of the current tier

        currentPodNodes = (k//2)**(t-1) # Number of top-tier nodes
        topTier = t # The starting tier, and the highest tier in the topology
        currentTier = t # Tracking the tiers as it iterates down them

        southboundPorts = k # Start with top-tier having all southbound ports

        while currentTierPrefix:
            currentPrefix = currentTierPrefix.pop(0)
            nodeNum = 0 # The number associated with a given node, appended after the prefix (ex: 1-1-1, pod 1-1, node number 1)

            for node in range(1,currentPodNodes+1):
                northNode = self.generateNodeName(currentPrefix, str(node), currentTier, topTier)

                for intf in range(1, southboundPorts+1):
                    # Per BFS logic, mark the neighbor as visited if it has not already, add to queue
                    # All tiers > 2
                    if(currentTier > self.LOWEST_SPINE_TIER):
                        southPrefix = self.generatePrefix(currentPrefix, str(intf))
                        self.determinePrefixVisitedStatus(southPrefix, nextTierPrefix)
                        southNodeNum = (nodeNum % (currentPodNodes // (k//2))) + 1

                    # The Leaf tier needs to have the same prefix of the spine tier (tier-2), as that is the smallest unit (pod)
                    elif(currentTier == self.LOWEST_SPINE_TIER):
                        southPrefix = currentPrefix
                        self.determinePrefixVisitedStatus(southPrefix, nextTierPrefix)
                        southNodeNum = intf

                    # Tier 1 connects to Tier 0, the compute nodes.
                    elif(currentTier == self.LEAF_TIER):
                        southPrefix = northNode.strip(self.LEAF_NAME)
                        southNodeNum = intf

                    southNode = self.generateNodeName(southPrefix, str(southNodeNum), currentTier-1, topTier)

                    self.addConnectionToGraph(northNode, southNode, currentTier, currentTier-1)

                    info(f"Connecting {northNode} and {southNode}\n")

                nodeNum += 1

            if(not currentTierPrefix):
                currentTierPrefix = deepcopy(nextTierPrefix)
                nextTierPrefix.clear()

                # If the top tier was just connected with its soutbound neighbors
                if(currentTier == topTier):
                    southboundPorts = k//2 # All tiers except the top have half of their ports southbound

                    # Proper distribution of links for 2-tier topologies
                    if(topTier == self.LOWEST_SPINE_TIER):
                        currentPodNodes = k

                # The number of connections in the next tier below will be cut down appropriately
                if(currentTier > self.LOWEST_SPINE_TIER):
                    currentPodNodes = currentPodNodes // (k//2)

                currentTier -= 1 # Now that the current tier is complete, move down to the next one

        return

    def isNotValidClosInput(self, k):
        '''
        Determine if 1:1 link overloading is occuring for topology
        '''

        if(k % 2 != 0):
            return True
        else:
            return False
        
    def generateNodeName(self, prefix, nodeNum, currentTier, topTier):
        '''
        Build the name for a given node based on its topology placement
        '''

        name = self.getNodeTitle(currentTier, topTier)

        if(currentTier == topTier):
            name += "_"
        else:
            name += prefix + "_"

        name += nodeNum

        return name
    
    def getNodeTitle(self, currentTier, topTier):
        '''
        Start the node naming process by determining what type of node it is
        based on the tier it is placed in.
        '''

        if(currentTier == topTier):
            title = self.TOF_NAME    
        elif(currentTier > 1):
            title = self.SPINE_NAME
        elif(currentTier == 1):
            title = self.LEAF_NAME
        else:
            title = self.COMPUTE_NAME
        
        return title
    
    def determinePrefixVisitedStatus(self, prefix, prefixList):
        '''
        Determine if a specific tier and pod has been visited yet.
        '''
        
        if(prefix not in prefixList):
            prefixList.append(prefix)

        return
    
    def generatePrefix(self, prefix, addition):
        '''
        Create a prefix name, which represents a tier and pod.
        '''

        return prefix + "-" + addition
    
    def addConnectionToGraph(self, northNodeName, southNodeName, northTier, southTier):
        '''
        Add the north-south (adjacent tier) connection between two nodes, either switch-switch or switch-host.
        '''
        
        if(northNodeName not in self.addedNodes):
            northNode = self.defineNode(northNodeName, northTier)
            self.addedNodes[northNodeName] = northNode
        else:
            northNode = self.addedNodes[northNodeName]

        if(southNodeName not in self.addedNodes):
            southNode = self.defineNode(southNodeName, southTier)
            self.addedNodes[southNodeName] = southNode
        else:
            southNode = self.addedNodes[southNodeName]

        self.nodeInfo(northNodeName)["southbound"].append(southNodeName)        
        self.nodeInfo(southNodeName)["northbound"].append(northNodeName)

        self.addLink(northNode, southNode)

        return
    
    def defineNode(self, nodeName, tier):
        '''
        Determines if the node in question is a Host or Switch
        '''

        attrs = {"northbound": [], "southbound": [], "tier": tier}

        # If the node is a client, add as a Mininet Host on the network
        if(nodeName.startswith(self.COMPUTE_NAME)):
            node = self.addHost(nodeName, attr_dict=attrs)

        # If the node is a switch, add as a Mininet Switch on the network
        else:
            node = self.addSwitch(nodeName, attr_dict=attrs)

        return node

# Add topology to custom option.
topos = { 'foldedclostopo': (lambda k, t: FoldedClosTopo(k, t)) }