# Network Vulnerability Analysis Tool

import nmap
import socket

def scan_network(ip_range):
    nm = nmap.PortScanner()
    nm.scan(ip_range, arguments='-sV')
    return nm.all_hosts()

def check_vulnerabilities(host):
    vulnerabilities = []
    try:
        # Example vulnerability checks
        if nm[host]['tcp'][22]['state'] == 'open':
            vulnerabilities.append('SSH port 22 is open')
        if nm[host]['tcp'][80]['state'] == 'open':
            vulnerabilities.append('HTTP port 80 is open')
    except KeyError:
        pass
    return vulnerabilities

def main():
    ip_range = '192.168.1.0/24'  # Change to your network range
    hosts = scan_network(ip_range)
    
    for host in hosts:
        print(f'Scanning host: {host}')
        vulnerabilities = check_vulnerabilities(host)
        if vulnerabilities:
            print(f'Vulnerabilities found on {host}: {vulnerabilities}')
        else:
            print(f'No vulnerabilities found on {host}')

if __name__ == "__main__":
    main()
