hostname ${node_name}
!
frr defaults datacenter
!
log file /tmp/${node_name}.log
log timestamp precision 3
!
debug bgp updates in
debug bgp updates out
debug bgp updates detail
debug zebra events
% if bfd:
!
bfd
 profile lowerIntervals
  transmit-interval 100
 !
% for neighbor in neighbors:
 peer ${neighbor["ip"]}
  profile lowerIntervals
  no shutdown
% endfor
!
exit
% endif
!
router bgp ${bgp_asn}
 timers bgp 1 3
 bgp log-neighbor-changes
% for neighbor in neighbors:
 neighbor ${neighbor["ip"]} remote-as ${neighbor["asn"]}
 % if bfd:
 neighbor ${neighbor["ip"]} bfd
 % endif
% endfor
 !
% if networks:
 address-family ipv4 unicast
% for network in networks:
  network ${network}
% endfor
 exit-address-family
% endif
exit