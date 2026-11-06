# 검수 사이트 주소 불일치 복구 — 2026-11-06

**현재 검수 사이트는 https://pc13.tail37c267.ts.net/ 이다.** 사용자가 새 주소 유지를 선택했다. 기존 자료 3,625개와 저장 판정 2,673개, 배정·수정 이력·계정·세션 secret을 보존하고 공개 접속을 복구했다. 수량은 복구 시점 snapshot이다.

## 원인과 조치

- PC13 SSH와 검수 task/loopback8770은 실행 중이었다. 기존 공개 주소 `yu-desktop-97msr1i.tail37c267.ts.net`은 DNS 조회에 실패했다.
- Tailscale Self DNSName/CertDomains는 이미 `pc13.tail37c267.ts.net`이었지만 Funnel은 예전 domain만 연결했고, 앱 `public_url` 및 Host/Origin 검증도 예전 주소를 사용했다. 장치 이름이 누가 언제 변경했는지는 이번 진단으로 확정하지 않았다.
- loopback IP로 직접 요청한 HTTP400은 Host 검증 때문이다. 기존 configured Host를 지정하면 로그인200으로 앱이 정상임을 구분했다.
- 기존 DB/config consistent backup과 Funnel 설정 export 후, 기존 포트8770의 공개 연결을 `tailscale funnel --bg --yes 8770`으로 현재 domain에 등록했다. 앱 config는 **public_url 한 항목만** 바꾸고 기존 task만 재시작했다. Host/Origin/CSRF 보안 검사를 완화하지 않았다.
- Windows hostname·Tailscale 장치명·SSH 계정/alias·기존 dataset/menu/question·학습 입력을 변경하지 않았다. 기존 Funnel route는 backup과 함께 보존했고 광범위 reset/down/up은 하지 않았다.
- 복구 중 기존 주소 유지 가능성을 문의받아 확인했지만, 이어진 사용자 결정으로 새 주소를 유지했다. 장치명을 과거 이름으로 변경하는 작업은 실행하지 않았다.

## 보존과 검증

- `team_review_status.inspect`의 모든 DB table count/hash·batch registry·prepared/reviewed 상태가 변경 전후 **완전히 일치**했다. 자료3,625 / 판정2,673 / 메뉴9개. Session secret hash도 동일했다. 운영 테스트 판정/배정0이다.
- 신규 origin을 사용하는 실제 config의 관리자 로그인·catalog·각 batch 경계 image smoke가 통과했다. 익명 접속과 Host/Origin/CSRF 관련 fixture를 포함한 `test_team_review.py` **13개 테스트 통과**.
- PC13 내부에서 새 Host의 `/login` HTTP200, 운영 task Running을 확인했다.
- 공개 DNS 응답의 ingress IP를 `curl --resolve`로 직접 지정해 tailnet 내부 DNS와 구분한 HTTPS 요청도 **HTTP200 / TLS verify0**을 확인했다. 인증서 검증은 끄지 않았다.
- 공개 새 주소에서 Edge Chromium의 Pixel7/iPhone13 viewport로 이름 선택, 전체3,625개/변경 source 수량, 공통 두 질문, 미검수량 정렬, old/new 이미지 HTTP200, 가로 overflow0을 확인했다. Claim 요청은 browser에서 가로채고 review POST를 차단했다. 실제 Safari·휴대폰 홈 화면 재설치는 이번에 검증하지 않았다.
- 제품 코드·dependency·학습 run을 바꾸지 않아 전체 모델 테스트는 반복하지 않았다. 초기 HTTPS 점검에는 SSL 오류/timeout이 있었고 후속 실제 HTTPS와 browser 성공 결과를 구분한다.

## 팀원 안내와 운영 경계

기존 즐겨찾기와 홈 화면 아이콘은 예전 domain을 가리킬 수 있다. **새 주소를 열어 본인 이름을 선택**하면 기존 서버 배정과 판정을 이어갈 수 있다. 홈 화면 아이콘도 새 주소에서 다시 추가한다. 옛 domain 자체가 해석되지 않아 앱의 HTTP redirect로 복구할 수는 없다.

Tailscale 장치명을 변경하면 공개 DNS/인증서 domain도 달라질 수 있다. 앞으로 PC13 이름을 바꿀 때는 실제 DNSName, Funnel, 앱 public_url, 공유 링크를 함께 확인한다. [공식 machine name 설명](https://tailscale.com/docs/concepts/machine-names), [Funnel CLI](https://tailscale.com/docs/reference/tailscale-cli/funnel).

PC13 원시 evidence/backup: ignored `data/review/hostname-recovery-20261106-v1/`의 `before-backup/`, `before-status.json`, `tailscale-serve-before.json`, `preparation.json`, `preservation.json`, `public-check-result.json`, `recover.py`, `restart.ps1`. 개발 PC의 ignored `data/work/hostname-recovery-20261106/`에는 browser QA와 소량 screenshot을 둔다. Raw DB·비밀값·실제 사용자 목록은 Git에 넣지 않는다.
