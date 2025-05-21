"""Custom topology built based on the content of a GraphML file

Two arguments are required, in the following order:
1. the path the graphML file.
2. The naming prefix of the hosts, if there are hosts. If there are no hosts, just simply add None.

Adding a topology with hosts in it (ex: host prefix is h, for h1, h2, etc.):
sudo mn --custom GraphmlTopo.py --topo=graphmltopo,"/home/pjw7904/MTP-Mininet/graphs/host_test.graphml",h
"""

from mininet.topo import Topo
import xml.dom.minidom # To parse the GraphML file

class GraphmlTopo(Topo):
    "Build a Mininet network with a GraphML file"

    def build(self, graphmlFilePath, clientPrefix=None):
        "Create a custom topo from a GraphML file"

        # Use an XML parser to parse the GraphML file
        graphmlFile = xml.dom.minidom.parse(graphmlFilePath)

        # Find all edges via the edge tag, add as Hosts and Links to Mininet network
        edges = graphmlFile.getElementsByTagName("edge")
        for edge in edges:

            # Add the nodes to the network
            sourceNode = self.defineNode(edge.getAttribute("source"), clientPrefix)
            targetNode = self.defineNode(edge.getAttribute("target"), clientPrefix)

            # Connect them together
            self.addLink(sourceNode, targetNode)

    def defineNode(self, nodeName, clientPrefix):
        "Determines if the node in question is a Host or Switch"

        # If the node is a client, add as a Mininet Host on the network
        if(clientPrefix is not None and nodeName.startswith(clientPrefix)):
            node = self.addHost(nodeName)

        # If the node is a switch, add as a Mininet Switch on the network
        else:
            node = self.addNode(nodeName)

        return node

topos = { 'graphmltopo': (lambda graphmlFilePath, clientPrefix: GraphmlTopo(graphmlFilePath, clientPrefix)) }