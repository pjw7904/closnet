#!/bin/bash

# A collection of commands to get Closnet ready to go by stopping processes that don't need to be running.

# Stop FRR
sudo service frr stop

# Stop Open vSwitch and all of the processes it creates
sudo systemctl stop openvswitch-switch

# Clean up Mininet, just in case
sudo mn --clean
