# Core libraries
from ipaddress import IPv4Network

# Custom libraries
from closnet.ClosGenerator import ClosGenerator


class BGPClosConfig(ClosGenerator):
    # BGP constants.
    PROTOCOL = "BGP"
    PRIVATE_ASN_RANGE_START = 64512

    # IPv4 network constants.
    LEAF_SPINE_SUPERNET = '172.16.0.0/12'
    COMPUTE_SUPERNET = '192.168.0.0/16'
    LEAF_SPINE_SUBNET_BITS = 12
    COMPUTE_SUBNET_BITS = 8

    # Security node Constants.
    FIRST_TOF_NODE_NAME = "T-1"
    SEC_NAME = "H" # H for hacker.
    SEC_TIER = -1

    def __init__(self, k, t, southboundPortsConfig=None, singleComputeSubnet=False, addSecurityNode=False):
        """
        Initializes a graph and its data structures to hold network information.

        :param k: Degree shared by each node.
        :param t: Number of tiers in the graph.
        :param name: The name you want to give the topology.
        "param singleComputeSubnet: If only one compute subnet should be attached to a leaf node.
        """

        # Call superclass constructor to get graph setup
        super().__init__(k, t, southboundPortsConfig)

        # Configure how BGP will assign ASNs and IPv4 addressing
        self.ASNAssignment = {None : None}
        self.currentASN = self.PRIVATE_ASN_RANGE_START
       
        # Define the address space for the core and edge networks
        self.coreNetworks = list(IPv4Network(self.LEAF_SPINE_SUPERNET).subnets(prefixlen_diff=self.LEAF_SPINE_SUBNET_BITS))
        self.edgeNetworks = list(IPv4Network(self.COMPUTE_SUPERNET).subnets(prefixlen_diff=self.COMPUTE_SUBNET_BITS))
        
        # If only one compute subnet should be hanging off a leaf, then each leaf needs to be given a specific subnet
        self.singleComputeSubnet = singleComputeSubnet
        self.leafComputeSubnets = {}

        # A security node can be added to a top-tier node if desired.
        self.addSecNode = True if addSecurityNode else False
        
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

        if(currentTier == topTier):
            partialName = title + "_"
        else:
            partialName = title + prefix + "_"

        # Add the unique number given to this node in the pod.
        name = partialName + nodeNum

        ASNPrefix = None

        # Compute and security nodes don't get an ASN
        if(title != self.COMPUTE_NAME and title != self.SEC_NAME):
            # Every leaf gets its own ASN
            if(title == self.LEAF_NAME):
                ASNPrefix = name

            # Spines in a pod get the same ASN
            elif(title == self.TOF_NAME or title == self.SPINE_NAME):
                ASNPrefix = partialName
            
            # Only give the node a new ASN if its a new spine pod or a leaf.
            if(ASNPrefix not in self.ASNAssignment):
                self.ASNAssignment[ASNPrefix] = self.currentASN
                self.currentASN += 1

        # I'm not sure if the conditional is needed here in a new function, but it was used successfully in the base class
        if(name not in self.clos):
            self.clos.add_node(name, northbound=[], southbound=[], tier=None, ASN=self.ASNAssignment[ASNPrefix], ipv4={}, advertise=[])

        # Return just the name, not the node object iself
        return name
   
    def connectNodes(self, northNode, southNode, northTier, southTier):
        """
        Connect two nodes together via an edge. Also configure the BGP ASN number and IP addressing.

        :param northNode: The node in tier N.
        :param southNode: The node in tier N-1.
        :param northTier: The tier value N.
        :param southTier: The tier value N-1.
        """

        isComputeNetwork = False

        # If one of the nodes is a compute node, this is an edge network (compute-leaf).
        if(southTier <= self.COMPUTE_TIER):
            self.addressEdgeNodes(northNode, southNode)
            isComputeNetwork = True

        # Otherwise, it is a core network (leaf-spine or spine-spine).
        else:
            self.addressCoreNodes(northNode, southNode)
        
        # Log the new information given to each node.
        self.clos.nodes[northNode]["southbound"].append(southNode)
        self.clos.nodes[northNode]["tier"] = northTier

        self.clos.nodes[southNode]["northbound"].append(northNode)
        self.clos.nodes[southNode]["tier"] = southTier
        
        # Add the edge to the topology, while also noting the type of network.
        self.clos.add_edge(northNode, southNode, computeNetwork=isComputeNetwork)

        # If a security node is requested, add it to the first (T-1) top-tier spine.
        if(self.addSecNode and northNode == self.FIRST_TOF_NODE_NAME):
            self.connectSecurityNode(northNode, northTier)
            
        return

    def connectSecurityNode(self, networkingNode, topTier):
        """
        Connect a networking node and a security/hacker node together via an edge.

        :param networkingNode: The networking/BGP node attached to the hacker node.
        """
        SEC_NODE_NUM = "1"

        self.addSecNode = False # Only add this node.
        

        securityNode = self.generateNode(self.SEC_NAME, SEC_NODE_NUM, self.SEC_TIER, topTier,)
        self.connectNodes(networkingNode, securityNode, topTier, self.SEC_TIER)

        return

    def addressEdgeNodes(self, northNode, southNode):
        """
        Provide IPv4 addressing to nodes on edge networks (leaf-compute).

        :param northNode: The node in tier N.
        :param southNode: The node in tier N-1.
        """
        
        NEXT_SUBNET = 0

        # If a single compute subnet is already defined for the leaf, reuse it and don't generate a new edge subnet. 
        if(northNode in self.leafComputeSubnets):
            subnet = self.leafComputeSubnets[northNode]
            #self.clos.nodes[northNode]["ipv4"][southNode] = self.clos.nodes[northNode]["ipv4"]["compute"]

        else:
            # Get next available edge subnet.
            subnet = list(self.edgeNetworks.pop(NEXT_SUBNET))[:-1] # Remove broadcast address.

            networkAddress = subnet.pop(0) # Grab the network address to be advertised by BGP.
            northAddress = subnet.pop() # Grab the last host address for the leaf node on the network.

            # Add subnet advertisement information to leaf node.
            self.clos.nodes[northNode]["advertise"].append(f"{networkAddress}/24")

            # Determine if an edge subnet needs to be reused and add addressing information to leaf node.
            if(self.singleComputeSubnet):
                self.leafComputeSubnets[northNode] = subnet
                self.clos.nodes[northNode]["ipv4"]["compute"] = str(northAddress)
            else:
                self.clos.nodes[northNode]["ipv4"][southNode] = str(northAddress)


        southAddress = subnet.pop(0) # Grab the next available low host address for the compute node on the network.

        # Add addressing information to compute node.
        self.clos.nodes[southNode]["ipv4"][northNode] = str(southAddress)

        return

    def addressCoreNodes(self, northNode, southNode):
        """
        Provide IPv4 addressing to nodes on core networks (leaf-spine or spine-spine).

        :param northNode: The node in tier N.
        :param southNode: The node in tier N-1.
        """
        
        NEXT_SUBNET = 0
 
        # Get next available core subnet.
        subnet = list(self.coreNetworks.pop(NEXT_SUBNET))[1:-1] # Remove network and broadcast address.

        northAddress = subnet.pop(0) # Grab the next available low host address.
        southAddress = subnet.pop(0)

        # Add addressing information to core nodes.
        self.clos.nodes[northNode]["ipv4"][southNode] = str(northAddress)
        self.clos.nodes[southNode]["ipv4"][northNode] = str(southAddress)

        return

    def jsonGraphInfo(self):
        '''
        Get a JSON-formatted output of the graph information
        
        :returns: JSON object containing the folded-Clos configuration.
        '''

        jsonData = {"sharedDegree": self.sharedDegree, 
                    "numTiers": self.numTiers,
                    "protocol": self.PROTOCOL}

        for tier in reversed(range(self.SEC_TIER, self.numTiers+1)):
            nodes = [v for v in self.clos if self.clos.nodes[v]["tier"] == tier]
            jsonData[f"tier_{tier}"] = {}

            for node in sorted(nodes):
                asn = self.clos.nodes[node]["ASN"]
                jsonData[f"tier_{tier}"][node] = {f"ASN": asn,
                                                  "advertisedRoutes": [],
                                                  "northbound": [], 
                                                  "southbound": []}

                for route in self.clos.nodes[node]["advertise"]:
                    jsonData[f"tier_{tier}"][node]["advertisedRoutes"].append(route)

                for northNode in self.clos.nodes[node]["northbound"]:
                    addr = self.clos.nodes[node]["ipv4"][northNode]
                    jsonData[f"tier_{tier}"][node]["northbound"].append(f"{northNode} - {addr}")

                if(tier == self.LEAF_TIER and self.singleComputeSubnet):
                    addr = self.clos.nodes[node]["ipv4"]["compute"]
                    jsonData[f"tier_{tier}"][node]["southbound"].append(f"compute - {addr}")
                else:
                    for southNode in self.clos.nodes[node]["southbound"]:
                        addr = self.clos.nodes[node]["ipv4"][southNode]
                        jsonData[f"tier_{tier}"][node]["southbound"].append(f"{southNode} - {addr}")

        return jsonData
    
    def isNetworkNode(self, node):
        return False if node == "compute" else self.clos.nodes[node]["tier"] > self.COMPUTE_TIER

    def isSecurityNode(self, node):
        return True if node.startswith(self.SEC_NAME) else False

    def iterNetwork(self, fabricFormating=False):
        """
        Iterator for the networks in the folded-Clos topology. 
        For core networks, this means every edge is its own network. For edge networks, it is either every edge, or its all edges connected to the same leaf if a single subnet is defined. 
        
        :return: Yield the current network.
        """

        processedleafNodes = set()
        
        for network in self.getNetworks():
            networkType = "edge" if self.clos.edges[network]["computeNetwork"] else "core"
            
            if(networkType == "core" or self.singleComputeSubnet == False):
                yield (network, self.generateFabricNetworkName(network, networkType)) if fabricFormating else network

            else:
                leaf = network[0] if network[0].startswith(self.LEAF_NAME) else network[1]

                if(leaf not in processedleafNodes):

                    # Get the leaf southbound and then convert to tuple
                    computeNetwork = (leaf,) + tuple(self.clos.nodes[leaf]["southbound"])

                    processedleafNodes.add(leaf)
                    
                    yield (computeNetwork, self.generateFabricNetworkName(network, networkType)) if fabricFormating else computeNetwork

    def generateFabricNetworkName(self, network, networkType):
        if(networkType == "edge"): 
            if(self.singleComputeSubnet == True):
                name = f"edge-{network[0]}-compute" # network[0] will always be the leaf when iterNetwork is called
            else:
                name = f"edge-{network[0]}-{network[1]}"
        else:
            if(self.clos.nodes[network[0]]["tier"] > self.clos.nodes[network[1]]["tier"]):
                name = f"core-{network[0]}-{network[1]}"
            else:
                name = f"core-{network[1]}-{network[0]}"

        return name

    def generateFabricIntfName(self, node, network):
        otherNode = network[1] if network[0] == node else network[0]

        if(self.clos.nodes[node]["tier"] == self.LEAF_TIER and self.clos.nodes[otherNode]["tier"] == self.COMPUTE_TIER and self.singleComputeSubnet == True):
            #intfName = f"{node}-intf-compute"
            intfName = f"intf-compute"
        else:
            #intfName = f"{node}-intf-{otherNode}"
            intfName = f"intf-{otherNode}"

        return intfName