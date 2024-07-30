#ifndef CONFIG_H
#define CONFIG_H

/*
 * Standard library imports.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <ifaddrs.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <stdbool.h>
#include <sys/stat.h>
#include <errno.h>

/*
 * Custom MTP imports.
 */
#include "mtp_utils.h" // Access MTP constants.

/*****************************************
 * CONSTANTS 
 *****************************************/
#define MAX_FILE_PATH_LENGTH 1024

/*****************************************
 * STRUCTURES 
 *****************************************/
/*
    Defines the configuration given by the configuration file 
    and the interface of the compute subnet if its a leaf.
*/
typedef struct Config {
    bool isLeaf;
    bool isTopSpine;
    uint8_t tier;
    char computeIntfName[ETH_LEN];
} Config;

/*****************************************
 * FUNCTION PROTOTYPES 
 *****************************************/
void readConfigurationFile(Config *config, const char* configFile);
int isValidDirectory(const char *path);
char* getConfigFilePath(const char* directory, const char* name);

#endif