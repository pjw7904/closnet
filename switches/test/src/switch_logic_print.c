#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>

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
}

int main(int argc, char *argv[]) 
{
    if (argc != 2) 
    {
        fprintf(stderr, "Usage: %s <node_name>\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    // Run the function
    print_interfaces(argv[1]);

    return 0;
}
