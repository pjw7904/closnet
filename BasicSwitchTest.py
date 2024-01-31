'''
author: Peter Willis (pjw7904@rit.edu)

Testing out the custom topology and switch found in this directory.
'''

# Mininet libraries
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI

# Custom code
from BasicCustomSwitch import TestSwitch
from GraphmlTopo import GraphmlTopo

def main():
    '''
    Running a Mininet experiment with a custom topolology and Switch.
    '''

    # Define the topology type
    testTopology = GraphmlTopo("graphs/triangle.graphml")

    # Define the network
    net = Mininet(topo=testTopology, 
                  switch=TestSwitch, 
                  controller=None)

    # Run the experiment
    net.start()
    CLI(net)
    net.stop()
    
    return

if __name__ == '__main__':
    setLogLevel('info')
    main()