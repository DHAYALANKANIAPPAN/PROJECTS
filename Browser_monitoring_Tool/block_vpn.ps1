# ========================
# BLOCK VPN TRAFFIC BY PORTS
# ========================

# Block common VPN UDP ports
$vpnPorts = @(1194, 500, 4500, 1701)
foreach ($port in $vpnPorts) {
    New-NetFirewallRule -DisplayName "Block VPN UDP $port" -Protocol UDP -LocalPort $port -Action Block
    Write-Host "[+] Blocking UDP port $port for VPN traffic"
}

# Optional: block TCP 443 if you want to prevent SSL-based VPNs (careful)
# New-NetFirewallRule -DisplayName "Block VPN TCP 443" -Protocol TCP -LocalPort 443 -Action Block

# ========================
# DISABLE VPN NETWORK ADAPTERS
# ========================
# Disable adapters containing common VPN keywords (TAP/TUN/PPP/VPN)
$vpnAdapters = Get-NetAdapter | Where-Object {$_.Name -match "tap|tun|ppp|vpn"}
foreach ($adapter in $vpnAdapters) {
    Disable-NetAdapter -Name $adapter.Name -Confirm:$false
    Write-Host "[+] Disabled VPN adapter: $($adapter.Name)"
}

# ========================
# OPTIONAL: Kill Known VPN Processes (backup)
# ========================
$vpnProcesses = @("nordvpn","expressvpn","surfshark","openvpn","protonvpn","windscribe","vpntunnel","vpnc")
foreach ($proc in Get-Process) {
    foreach ($vpn in $vpnProcesses) {
        if ($proc.ProcessName -match $vpn) {
            Stop-Process -Id $proc.Id -Force
            Write-Host "[!] Killed VPN process: $($proc.ProcessName)"
        }
    }
}

Write-Host "[+] VPN blocking script applied successfully!"
####################################
###################################
###############################
##############################################
############
###########Instructions to Run

#Open PowerShell as Administrator.

#Save the above code as block_vpn.ps1.

#Run the script:  Set-ExecutionPolicy RemoteSigned -Scope CurrentUser.\block_vpn.ps1
