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
!
router bgp ${bgp_asn}
 timers bgp 1 3
% for neighbor in neighbors:
 neighbor ${neighbor["ip"]} remote-as ${neighbor["asn"]}
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