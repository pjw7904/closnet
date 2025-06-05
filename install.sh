#!/bin/bash

############################################
# INSTALL BASE DEPENDENCIES
echo "Installing Python and curl..."

apt update & apt install -y python3 python3-pip curl

mkdir logs
############################################

############################################
# INSTALL MININET
echo "Installing Mininet..."

apt install -y mininet
############################################

############################################
# INSTALL FRR

echo "Installing FRR..."

## add GPG key
curl -s https://deb.frrouting.org/frr/keys.gpg | tee /usr/share/keyrings/frrouting.gpg > /dev/null

## frr-stable will be the latest official stable release
FRRVER="frr-stable"
echo deb '[signed-by=/usr/share/keyrings/frrouting.gpg]' https://deb.frrouting.org/frr \
     $(lsb_release -s -c) $FRRVER | tee -a /etc/apt/sources.list.d/frr.list

apt install -y frr frr-pythontools

# Give permissions to user to access frr files (this requires a logout after to take effect)
usermod -a -G frr,frrvty $(logname)
############################################

############################################
# INSTALL ADDITIONAL DEPENDENCIES

if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
else
    echo "requirements.txt not found, skipping Python dependencies installation."
fi

echo "Installing additional dependencies..."

sudo DEBIAN_FRONTEND=noninteractive apt -y install tshark

############################################
# INSTALL & COMPILE MTP IMPLEMENTATION

# Install build-essential for compiling C code
# Install additional dependencies inferred from C code
# Assuming possible use of networking libraries and logging
echo "Installing C development tools..."

apt install -y build-essential autoconf automake libtool bison flex gdb cmake pkg-config libpcap-dev

# Create a directory for the MTP binary
mkdir closnet/protocols/mtp/bin

# Compile MTP source files
MTP_SRC_DIR="closnet/protocols/mtp/src"
MTP_BIN="closnet/protocols/mtp/bin/mtp"

if [ -d "$MTP_SRC_DIR" ]; then
    echo "Compiling MTP source files..."
    gcc $MTP_SRC_DIR/*.c -o $MTP_BIN
else
    echo "MTP implementation source directory not found, skipping compilation."
fi
############################################

# Final message
echo "Installation and setup is almost complete. Please restart your system before using Closnet."
