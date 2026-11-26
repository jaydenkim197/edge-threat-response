[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('pc11', 'pc12', 'pc13', 'pc14')]
    [string]$Target
)

$ErrorActionPreference = 'Stop'
$inventory = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'targets.json') -Raw | ConvertFrom-Json
$sender = @($inventory.nodes | Where-Object { $_.hostname -eq $env:COMPUTERNAME })
$peer = @($inventory.nodes | Where-Object { $_.id -eq $Target })
if ($sender.Count -ne 1 -or $peer.Count -ne 1 -or $sender[0].id -eq $Target) {
    throw 'Run this command on a configured PC and choose one of its peers.'
}
$sender = $sender[0]
$peer = $peer[0]
$localIp = [System.Net.IPAddress]::Parse($sender.lan_ip)
$peerIp = [System.Net.IPAddress]::Parse($peer.lan_ip)
$nic = @(Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' -and $_.MacAddress -eq $sender.mac })
if ($nic.Count -ne 1) { throw 'The configured physical Ethernet adapter is unavailable.' }
$lan = @(Get-NetIPAddress -InterfaceIndex $nic[0].ifIndex -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -eq $localIp.IPAddressToString -and $_.AddressState -eq 'Preferred' })
if ($lan.Count -ne 1 -or $lan[0].PrefixLength -ne 24) {
    throw 'The configured Ethernet IPv4 address or subnet has changed.'
}
$network = $localIp.GetAddressBytes()
$destination = $peerIp.GetAddressBytes()
if ($destination.Length -ne 4 -or (0..2 | Where-Object { $network[$_] -ne $destination[$_] })) {
    throw 'The target is outside the local Ethernet subnet.'
}
$network[3] = 255
$broadcast = [System.Net.IPAddress]::new($network)
if ($peer.mac -notmatch '^(?:[0-9A-F]{2}-){5}[0-9A-F]{2}$') { throw 'Invalid target MAC address.' }
[byte[]]$mac = $peer.mac.Split('-') | ForEach-Object { [Convert]::ToByte($_, 16) }
[byte[]]$packet = (@(255) * 6) + ($mac * 16)
$source = [System.Net.IPEndPoint]::new($localIp, 0)
$endpoint = [System.Net.IPEndPoint]::new($broadcast, 9)
$client = [System.Net.Sockets.UdpClient]::new($source)
try {
    $client.EnableBroadcast = $true
    for ($i = 0; $i -lt 3; $i++) {
        if ($client.Send($packet, $packet.Length, $endpoint) -ne 102) { throw 'Incomplete magic packet send.' }
        if ($i -lt 2) { Start-Sleep -Milliseconds 150 }
    }
} finally {
    $client.Dispose()
}
Write-Output "$($sender.id) -> $($peer.id): sent 3 Wake-on-LAN packets."
