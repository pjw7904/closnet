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
void print_interfaces(const char* switch_name, const char* log_file) {
    struct ifaddrs *ifaddr, *ifa;
    int family, s;
    char host[NI_MAXHOST];
    FILE *file = fopen(log_file, "w");

    if (file == NULL) {
        perror("fopen");
        exit(EXIT_FAILURE);
    }

    if (getifaddrs(&ifaddr) == -1) {
        perror("getifaddrs");
        fclose(file);
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
            fprintf(file, "Interface: %s\n", ifa->ifa_name);

            // For an AF_INET* interface address, display the address
            if (family == AF_INET || family == AF_INET6) {
                s = getnameinfo(ifa->ifa_addr,
                                (family == AF_INET) ? sizeof(struct sockaddr_in) :
                                                      sizeof(struct sockaddr_in6),
                                host, NI_MAXHOST,
                                NULL, 0, NI_NUMERICHOST);
                if (s != 0) {
                    fprintf(file, "getnameinfo() failed: %s\n", gai_strerror(s));
                } else {
                    fprintf(file, "\tAddress: <%s>\n", host);
                }
            }
        }
    }

    freeifaddrs(ifaddr);
    fclose(file);
}

int main(int argc, char *argv[]) 
{
    if (argc != 2) 
    {
        fprintf(stderr, "Usage: %s <node_name>\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    char log_file[256];
    snprintf(log_file, sizeof(log_file), "%s.log", argv[1]);

    // Run the function
    print_interfaces(argv[1], log_file);

    return 0;
}
