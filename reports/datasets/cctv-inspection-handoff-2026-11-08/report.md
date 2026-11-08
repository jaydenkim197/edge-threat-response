# CCTV 평가 원본 전달 — 2026-11-08

사용자는 계속 관측되는 CCTV0/31에 대해 모델·라벨·전처리·평가 오류를 구분해 조사하되, 먼저 실제 평가 데이터를 직접 확인하도록 전달해 달라고 요청했다. 이번 단계는 **동일 입력 전달과 source 대응 검사**이며 전체 원인 분석을 완료한 것이 아니다.

- 입력: S1/M1/M2 공통 평가의 `us-mock-reviewed`, US Mock Attack 공개 CCTV83장. 현재 Knife 라벨 양성31장·객체31개, Knife 라벨0인 이미지52장이다. 연속 시나리오 영상이나 자체 P430 촬영이 아닌 공개 프레임 subset이다.
- 원본 이미지83장을 재인코딩 없이 복사하고 원본 XML83개·고정 평가 truth의 사본·상대 경로 manifest를 함께 보관했다. 이미지마다 현재 Knife GT만 초록색으로 표시한 전체 프레임83장과 칼 라벨 확대31개·모아보기를 생성했다. 모델 예측은 이 첫 묶음에 넣지 않았다.
- 원본 ZIP 이미지와 실제 평가 이미지의 byte SHA가83개 모두 일치했다. XML의 source class 이름 `Knife`를 직접 읽은31개 박스의 개수·좌표와 평가 truth도 일치했다. 원본 XML에는 `Handgun`91개, `Short_rifle`15개가 함께 있다. Knife0인 프레임이 모든 weapon이 없는 프레임을 뜻하지 않는다.
- 고정 truth SHA-256: `61c08bd33a00f3036eda5fb8df2824cc6a223d0a0d94dcf94953e332887f1676`. source revision `07ced721cd90973f66806c0b3ee01e80c439ba90`, archive SHA `558f5baa109abe8fba57b61fa177c75358001f5499f5e78178f4bf7dc9f55e8c`. 기존 CC BY-NC4.0/학술 이용 안내를 유지하며 원본 이미지·XML·ZIP은 Git에 넣지 않는다.
- 현재 라벨의 의미가 실제 이미지에서 옳은지, 전처리/좌표 역변환/예측 클래스/평가 매칭이 옳은지는 아직 결론 내리지 않았다. source와 평가 라벨의 일치만으로 모델 문제라고 단정하지 않는다. frozen GT·이전 결과·검수 DB/배정/판정·학습·운영 모델은 변경하지 않았다.
- PC13 ignored 준비 경로: `data/work/cctv-inspection-20261108-v1`. 사용자에게 전달한 로컬 경로·수량·hash 검사 요약은 [전달 확인](delivery-summary.json)에 기록한다. 생성 코드는 같은 날짜의 ignored `runs/cctv-inspection-20261108/export_remote.py`/`unpack_local.py`에 남겼다.

다음은 사용자의 원본 확인을 바탕으로 같은 이미지에 M1/M2/S1 예측을 겹쳐 source 의미·입력/box 변환·matching을 대조하는 원인 분석이다. 의심 라벨을 자동 수정하거나 기존0/31을 근거 없이 취소하지 않는다. Git commit은 본 저장소 이력으로 추적한다.
