#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/stat.h> // For check of directory
#include <errno.h>


// Function to extract and print the number after "eth" in the interface name
void print_port_number(const char *ifa_name) 
{
    // Find the "eth" substring in ifa_name
    const char *eth_position = strstr(ifa_name, "eth");

    if (eth_position != NULL) 
    {
        // Move past the "eth" substring
        eth_position += 3;

        // Print the number following "eth"
        printf("\tPort number: %s\n", eth_position);
    }
}

// Mininet interfaces always start with the node name (ex: sw121-eth1), so we can use this to filter out the host interfaces.
void print_interfaces(const char* switch_name) 
{
    struct ifaddrs *ifaddr, *ifa;
    int family, s;
    char host[NI_MAXHOST];

    if (getifaddrs(&ifaddr) == -1) {
        perror("getifaddrs");
        exit(EXIT_FAILURE);
    }

    // Loop through linked list of interfaces
    for (ifa = ifaddr; ifa != NULL; ifa = ifa->ifa_next) {
        if (ifa->ifa_addr == NULL) {
            continue;
        }

        family = ifa->ifa_addr->sa_family;

        // CHECK IF THE INTERFACE NAME STARTS WITH THE SWITCH NAME.
        if (strncmp(ifa->ifa_name, switch_name, strlen(switch_name)) == 0) {
            // Print interface name
            printf("Interface: %s\n", ifa->ifa_name);

            // Print the port number (substring after the dash)
            print_port_number(ifa->ifa_name);

            // For an AF_INET* interface address, display the address
            if (family == AF_INET || family == AF_INET6) {
                s = getnameinfo(ifa->ifa_addr,
                                (family == AF_INET) ? sizeof(struct sockaddr_in) :
                                                      sizeof(struct sockaddr_in6),
                                host, NI_MAXHOST,
                                NULL, 0, NI_NUMERICHOST);
                if (s != 0) {
                    printf("getnameinfo() failed: %s\n", gai_strerror(s));
                } else {
                    printf("\tAddress: <%s>\n", host);
                }
            }
        }
    }

    freeifaddrs(ifaddr);

    return;
}


// Function to validate if a given path is a directory
int is_valid_directory(const char *path) 
{
    struct stat sb;

    // Check if the path exists and is a directory
    if(stat(path, &sb) == 0) 
    {
        if(S_ISDIR(sb.st_mode)) 
        {
            return 1;  // It's a valid directory
        } 
        
        else 
        {
            fprintf(stderr, "Error: '%s' exists but is not a directory.\n", path);
        }
    } 
    
    else 
    {
        fprintf(stderr, "Error: Cannot access '%s': %s\n", path, strerror(errno));
    }
    
    return 0;  // It's not a valid directory
}


int main(int argc, char *argv[]) 
{
    if(argc != 3) 
    {
        fprintf(stderr, "Usage: %s <node_name> <log_directory>\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    // Run the functions
    if(is_valid_directory(argv[2])) 
    {
        printf("'%s' is a valid directory.\n", argv[2]);
        // You can now safely pass this path to other functions
    } 
    else
    {
        fprintf(stderr, "Error: '%s' is not a valid directory.\n", argv[2]);
        return 1;
    }

    print_interfaces(argv[1]);

    return 0;
}
