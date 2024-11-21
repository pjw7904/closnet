# Closnet

An automation framework to build an emulated version of a modern data center network for experimentation of network protocols. It is built as an extension of Mininet, a popular network emulator.

The topology built is a traditional folded-Clos with a 1:1 oversubscription ratio, resulting in a rearrangably nonblocking network (hence the name Closnet). Closnet is able to determine the appropriate configuration necessary for connecting nodes, which can then be used to build configuration files for network protocols that utilize the hierarchical folded-Clos system. The figure below illustrates a high-level overview of a folded-Clos data center nework:

![2-tier, 4-port folded-Clos topology](docs/clos_example.png)

## Getting Started

### Prerequisites

Closnet has been tested on Ubuntu 22.04 and the installation script currentlly assumes that it is being run on a Debian-based system that can access the apt package manager.

Due to the libraries used and its reliance on Linux network namespaces, Closnet can only be run on Linux distributions. Future updates may allow for other Linux distributions beyond Debian and its derivatives.

### Installation

All necessary software is installed using the included installation script. Installing Closnet requires the following commands:

```bash
git clone https://github.com/pjw7904/closnet.git
cd closnet
sudo bash install.sh
```

Packages installed include:
* Python 3.X
* Mininet
* Free Range Routing (FRR)
* NetworkX
* Mako
* An implementation of the Meshed Tree Protocol for data center networks (MTP-DCN)

## Usage

Running Closnet requires information about the folded-Clos topology to be built and what protocol should be installed on the nodes. The command to start Closnet is as follows, where [protocol] and [options] are arguments to be added depending on the experiment to be run:

```bash
sudo python3 closnet [protocol] [options]
```

### Protocols

By default, Closnet includes two data center protocols to test.

| Protocol    | Description |
| ----------- | ----------- |
| mtp | A custom implementation of the [Meshed Tree Protocol for data center networks (MTP-DCN)](https://github.com/pjw7904/CMTP)|
| bgp | The Free Range Routing (FRR) implementation of the [Border Gateway Protocol (BGP)](https://docs.frrouting.org/en/latest/bgp.html) |

Included with these protocols are appropriate Mako template files to assist in automating the creation of configuration files for each node in the folded-Clos topology.

If additional protocols are desired, you must add the necessary information to a new `closnet/switches` sub-directory, including a Mininet switch/node sub-class along with a Mako configuration template and the binary file if necessary. Finally, the new protocol must be recognized in the main function. Both the mtp and bgp sub-directories provide examples of how to add a protocol to Closnet.

### Options

The folded-Clos topology configuration is describe in the options arguments.

| Option      | Description |
| ----------- | ----------- |
| `-t numOfTiers` or `--tiers numOfTiers` | The number of tiers in the folded-Clos topology, excluding the compute tier 0. |
| `-p numOfPorts` or `--ports numOfPorts` | The number of ports each switch has in the folded-Clos topology.|
| `-s SOUTHBOUND SOUTHBOUND` or `--southbound SOUTHBOUND SOUTHBOUND` | The number of links to a tier below by specficing the tier and the number of southbound ports per switch. |

### Example

Given the following Closnet command:

```bash
sudo python3 closnet mtp -t 3 -p 4 -s 1 1
```

The following topology is built with each node running MTP:

![3-tier, 4-port folded-Clos topology](docs/closnet_example.png)

## Viewing Node Data

Once Mininet is up and running, the current state of any given node can be determined by looking into its log file or by accessing its interactive shell.

### MTP

Logs are stored in the `/tmp` directory, with the following log files available to view for any given node (L_1 in this example):

```bash
user@system:/tmp$ ls | grep L_1
L_1.conf
L_1.log
L_1.stdout
L_1.down
```
| File      | Description |
| ----------- | ----------- |
| `.conf` | The MTP configuration file for the node. |
| `.log` | The MTP log file for the node describing protocol actions and updates. |
| `.stdout` | Any text which is meant to be printed to standard out or standard err is sent here. |
| `.down` | Created after the node is shutdown at the end of the test, the epoch time of shutdown. |

### BGP

Logs are stored in the `/tmp` directory, with the following log files available to view for any given node (L_1 in this example):

```bash
user@system:/tmp$ ls | grep L_1
L_1.bgpd.pid
L_1.conf
L_1.log
L_1.zebra.pid
```

| File      | Description |
| ----------- | ----------- |
| `.bgpd.pid` | PID file for bgpd, do not touch. |
| `.zebra.pid` | PID file for zebra, do not touch. |
| `.conf` | The FRR configuration file for the node. It contains BGP configuration. |
| `.log` | The FRR log file for the node describing BGP and Zebra actions and updates. |

FRR has an interactive shell (vtysh) to view and set configurations. You may access this shell for any given FRR node in a Closnet topology by opening a new tab and entering the following command:

```bash
vtysh -N [node_name]
```

Where [node_name] is the name of a Closnet node generated.

## Troubleshooting

The biggest issue with Mininet-based projects is having a topology fail and Mininet refusing to work after the fact. If this is the case, reset Mininet and your systems network namespace configuration with the command:

```bash
sudo mn --clean
```