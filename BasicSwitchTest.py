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
from BasicCustomSwitch import TestSwitch, CCodeSwitch
from topology_generators.GraphmlTopo import GraphmlTopo

def logTest():
    '''
    Running a Mininet experiment with a custom topolology and Switch.
    '''

    # Define the topology type
    testTopology = GraphmlTopo("graphs/triangle.graphml")

    # Define the network, use the TEST SWTICH
    net = Mininet(topo=testTopology, 
                  switch=TestSwitch, 
                  controller=None)

    # Run the experiment
    net.start()
    CLI(net)
    net.stop()
    
    return

def CCodeTest():
    '''
    Running a Mininet experiment with custom C code switches.
    '''

    # Define the topology type
    testTopology = GraphmlTopo("graphs/host_test.graphml", "h")

    # Define the network, use the C CODE SWITCH
    net = Mininet(topo=testTopology, 
                  switch=CCodeSwitch,
                  controller=None)

    # Run the experiment
    net.start()
    CLI(net)
    net.stop()
    
    return


if __name__ == '__main__':
    setLogLevel('info')
    CCodeTest()