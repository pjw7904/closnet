# Core libraries
from ipaddress import IPv4Network
from collections import defaultdict

# Custom libraries
from closnet.ClosGenerator import ClosGenerator


class MTPClosConfig(ClosGenerator):
    PROTOCOL = "MTP"

    COMPUTE_SUPERNET = '192.168.0.0/16'
    COMPUTE_SUBNET_BITS = 8

    def __init__(self, k, t, singleComputeSubnet=False, **kwargs):
        """
        Initializes a graph and its data structures to hold network information.

        :param k: Degree shared by each node.
        :param t: Number of tiers in the graph.
        :param name: The name you want to give the topology.
        "param singleComputeSubnet: If only one compute subnet should be attached to a leaf node.
        """

        # Call superclass constructor to get graph setup
        super().__init__(k, t, **kwargs)

        # Define the address space for the core and edge networks
        self.edgeNetworks = list(IPv4Network(self.COMPUTE_SUPERNET).subnets(prefixlen_diff=self.COMPUTE_SUBNET_BITS))
        
        # If only one compute subnet should be hanging off a leaf, then each leaf needs to be given a specific subnet
        self.singleComputeSubnet = singleComputeSubnet
        self.leafComputeSubnets = {}    
        
    def connectNodes(self, northNode, southNode, northTier, southTier):
        """
        Connect two nodes together via an edge. The nodes must be in adjacent tiers (ex: tier 2 and tier 3). 
        The nodes also understand if their new neighbor is above them (northbound) or below them (southbound). 

        :param northNode: The node in tier N.
        :param southNode: The node in tier N-1.
        :param northTier: The tier value N.
        :param southTier: The tier value N-1.
        """
        
        # Only add the nodes to the topology if they haven't already been added prior.
        if(northNode not in self.clos):
            self.clos.add_node(northNode, 
                               northbound=[], 
                               southbound=[], 
                               tier=northTier, 
                               ipv4=defaultdict(lambda: "MTP"), 
                               isTopTier=True if self.numTiers == northTier else False)
        if(southNode not in self.clos):
            self.clos.add_node(southNode, 
                               northbound=[], 
                               southbound=[], 
                               tier=southTier, 
                               ipv4=defaultdict(lambda: "MTP"), 
                               isTopTier=False)
        
        # Mark each other as neighbors in their appropriate direction.
        self.clos.nodes[northNode]["southbound"].append(southNode)
        self.clos.nodes[southNode]["northbound"].append(northNode)

        # If one of the nodes is a compute node, this is an edge network (compute-leaf).
        isComputeNetwork = False
        if(southTier == self.COMPUTE_TIER):
            isComputeNetwork = True
            self.addressEdgeNodes(northNode, southNode)
                 
        # Add the edge between the two nodes to the topology
        self.clos.add_edge(northNode, southNode, computeNetwork=isComputeNetwork)

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
        else:
            # Get next available edge subnet.
            subnet = list(self.edgeNetworks.pop(NEXT_SUBNET))[1:-1] # Remove network and broadcast address.

            northAddress = subnet.pop() # Grab the last host address for the leaf node on the network.

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
    
    def isNetworkNode(self, node):
        return False if node == "compute" else self.clos.nodes[node]["tier"] > self.COMPUTE_TIER

    def iterNetwork(self, fabricFormating=False):
        """
        Iterator for the networks in the folded-Clos topology. 
        For core networks, this means every edge is its own network. 
        For edge networks, it is either every edge, or its all edges connected to the same leaf if a single subnet is defined. 
        
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

    
    def jsonGraphInfo(self):
            '''
            Get a JSON-formatted output of the graph information
            
            :returns: JSON object containing the folded-Clos configuration.
            '''

            jsonData = {"protocol": self.PROTOCOL,
                        "tiers": self.numTiers,
                        "ports": self.sharedDegree
                        }

            for tier in reversed(range(self.numTiers+1)):
                nodes = [v for v in self.clos if self.clos.nodes[v]["tier"] == tier]
                jsonData[f"tier_{tier}"] = {}

                for node in sorted(nodes):
                    jsonData[f"tier_{tier}"][node] = {"northbound": [], 
                                                    "southbound": []}

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
