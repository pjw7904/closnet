#!/bin/bash

# MTP directories for the source code and binary 
MTP_SRC_DIR="closnet/protocols/mtp/src"
MTP_BIN="closnet/protocols/mtp/bin/mtp"

if [ -d "$MTP_SRC_DIR" ]; then
    sudo gcc $MTP_SRC_DIR/*.c -o $MTP_BIN
    echo "MTP implementation compilation attempt complete."
else
    echo "MTP implementation source directory not found, skipping compilation."
fi
