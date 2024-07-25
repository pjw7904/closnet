# Mininet libraries
from mininet.topo import Topo
from mininet.log import info

# External libraries
import networkx as nx

class ClosConfigTopo(Topo):
    # Tiers
    LOWEST_SPINE_TIER = 2
    LEAF_TIER = 1
    COMPUTE_TIER = 0

    def build(self, clos: nx.graph):
        self.clos = clos
        self.addedNodes = {}

        for edge in clos.edges:
            node1 = self.getNode(edge[0])
            node2 = self.getNode(edge[1])
            self.addLink(node1, node2)

        return


    def getNode(self, node: str):
        if(node not in self.addedNodes):
            if(self.clos.nodes[node]['tier'] > self.COMPUTE_TIER):
                mininetNode = self.addSwitch(node)

            elif(self.clos.nodes[node]['tier'] == self.COMPUTE_TIER):
                mininetNode = self.addHost(node)

            else:
                raise Exception(f"{node} does not have a normal tier value, not adding.")

            self.addedNodes[node] = mininetNode

        else:
            mininetNode = self.addedNodes[node]

        return mininetNode


# Add topology to custom option.
topos = { 'closconfigtopo': (lambda configFile: ClosConfigTopo(configFile)) }
