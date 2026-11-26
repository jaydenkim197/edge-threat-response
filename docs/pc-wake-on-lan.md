# PC11~14 Wake-on-LAN

각 PC의 `C:/Class6/etr-wol/Wake-PC.ps1`로 다른 세 대를 깨울 수 있다. 노트북에서는 켜져 있는 PC에 기존 Tailscale SSH로 명령을 보내면 된다. 예를 들어 PC11에서 PC14를 깨우려면 다음을 실행한다.

```powershell
ssh pc11 powershell -NoProfile -ExecutionPolicy Bypass -File C:/Class6/etr-wol/Wake-PC.ps1 pc14
```

첫 번째 `pc11`은 패킷을 보내는 PC이고 마지막 `pc14`는 대상 PC다. 보내는 PC는 최소 한 대 켜져 있어야 한다. 대상이 부팅된 뒤 평소처럼 SSH에 접속한다. 이 명령의 성공 메시지는 패킷 전송을 의미한다.

서버마다 같은 PowerShell 스크립트와 현장 장비 목록 `targets.json`을 별도로 설치했다. 스크립트는 대상과 자신의 물리 유선 LAN이 같은 /24인지 검사하고, 자신의 Ethernet IPv4에 바인딩해 UDP 9 매직 패킷을 세 번 보낸다. 설치에 상주 서버나 인바운드 포트 추가는 필요하지 않다.

2026-11-26 확인 결과, 네 대 모두 Windows의 `wake_armed` 목록에 유선 랜카드가 있었으며 Magic Packet과 드라이버의 Shutdown Wake-on-LAN이 활성화되어 있었다. SSH와 Tailscale 서비스는 자동 시작으로 확인했고, PC14의 Tailscale 무인 실행을 활성화했다. [Tailscale 무인 실행 문서](https://tailscale.com/docs/how-to/run-unattended).

네 PC에서 PktMon으로 유선 패킷을 수집해 12개 방향 모두에서 수신 PC의 MAC과 일치하는 102바이트 매직 패킷을 확인했다. 운영 중인 장비의 절전·종료·재부팅은 실행하지 않았으므로 실제 전원 전이는 미검증이다. 네 대 모두 기존 Fast Startup 설정을 유지했다. 절전 복귀와 달리 완전 종료 뒤 기동은 BIOS/UEFI·랜카드 대기 전원에 따라 달라진다. AC 전원 차단 시에는 LAN으로 켤 수 없다. [Microsoft 전원 상태와 WoL 설명](https://learn.microsoft.com/en-us/windows/win32/power/system-power-states).
