#!/bin/bash

############################################
# INSTALL BASE DEPENDENCIES
echo "Installing Python and curl..."

sudo apt update & sudo apt install -y python3 python3-pip curl
############################################

############################################
# INSTALL MININET
echo "Installing Mininet..."

sudo apt install mininet
############################################

############################################
# INSTALL FRR

echo "Installing FRR..."

## add GPG key
curl -s https://deb.frrouting.org/frr/keys.gpg | sudo tee /usr/share/keyrings/frrouting.gpg > /dev/null

## frr-stable will be the latest official stable release
FRRVER="frr-stable"
echo deb '[signed-by=/usr/share/keyrings/frrouting.gpg]' https://deb.frrouting.org/frr \
     $(lsb_release -s -c) $FRRVER | sudo tee -a /etc/apt/sources.list.d/frr.list

## update and install FRR
sudo apt update && sudo apt install -y frr frr-pythontools

# Give permissions to user to access frr files (this requires a logout after to take effect)
sudo usermod -a -G frr,frrvty $(logname)
############################################

############################################
# INSTALL ADDITIONAL PYTHON DEPENDENCIES

if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
else
    echo "requirements.txt not found, skipping Python dependencies installation."
fi

############################################
# INSTALL & COMPILE MTP IMPLEMENTATION

# Install build-essential for compiling C code
# Install additional dependencies inferred from C code
# Assuming possible use of networking libraries and logging
echo "Installing C development tools..."

sudo apt-get install -y build-essential autoconf automake libtool bison flex gdb cmake pkg-config libpcap-dev

# Compile MTP source files
MTP_SRC_DIR="closnet/switches/mtp/src"
MTP_BIN="closnet/switches/mtp/bin/mtp"

if [ -d "$MTP_SRC_DIR" ]; then
    echo "Compiling MTP source files..."
    sudo gcc $MTP_SRC_DIR/*.c -o $MTP_BIN
else
    echo "MTP implementation source directory not found, skipping compilation."
fi
############################################

# Final message
echo "Installation and setup is almost complete. Please restart your system before using Closnet."
