# Mininet libraries
from mininet.topo import Topo

# External libraries
import networkx as nx

class ClosConfigTopo(Topo):
    # Tiers
    LOWEST_SPINE_TIER = 2
    LEAF_TIER = 1
    COMPUTE_TIER = 0

    def build(self, clos: nx.graph) -> None:
        self.clos = clos
        self.addedNodes = {}

        for edge in clos.edges():
            # Add the nodes to the topology
            node1 = self.getNode(edge[0])
            node2 = self.getNode(edge[1])

            # Configure IPv4 addressing if necessary
            node1Address, node2Address = self.getIPv4Addressing(node1, node2)

            # Add the link between the nodes to the topology
            self.addLink(node1, node2, 
                         params1=node1Address, params2=node2Address)

        return


    def getNode(self, node: str):
        if(node not in self.addedNodes):
            if(self.clos.nodes[node]['tier'] > self.COMPUTE_TIER):
                mininetNode = self.addSwitch(node)

            elif(self.clos.nodes[node]['tier'] == self.COMPUTE_TIER):
                hostIPDict = self.clos.nodes[node].get('ipv4')
                defaultGateway = list(hostIPDict.keys())[0]
                hostIP = list(hostIPDict.values())[0]
                    
                mininetNode = self.addHost(node, 
                                           ip=f"{hostIP}/24", defaultRoute=f"via {self.clos.nodes[defaultGateway]['ipv4'][node]}")

            else:
                raise Exception(f"{node} does not have a normal tier value, not adding.")

            self.addedNodes[node] = mininetNode

        else:
            mininetNode = self.addedNodes[node]

        return mininetNode


    def getIPv4Addressing(self, node1: str, node2: str) -> tuple:
        node1Address = None
        node2Address = None

        if node2 in self.clos.nodes[node1]['ipv4']:
            node1Address = {'ip': f"{self.clos.nodes[node1]['ipv4'][node2]}/24"}

        if node1 in self.clos.nodes[node2]['ipv4']:
            node2Address = {'ip': f"{self.clos.nodes[node2]['ipv4'][node1]}/24"}

        return node1Address, node2Address


# Add topology to custom option.
topos = { 'closconfigtopo': (lambda configFile: ClosConfigTopo(configFile)) }
