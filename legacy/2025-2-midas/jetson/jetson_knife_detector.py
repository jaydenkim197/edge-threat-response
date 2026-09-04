#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson Nano용 칼 감지 시스템
- 카메라로 실시간 칼 감지
- 칼 감지 시 LED 켜고 부저 울림
"""

import torch
import cv2
import time
import Jetson.GPIO as GPIO

# GPIO 설정
LED_PIN = 12      # LED 연결 핀 (필요시 변경)
BUZZER_PIN = 18   # 부저 연결 핀 (필요시 변경)

GPIO.setmode(GPIO.BOARD)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

# YOLOv5 모델 로드
print("모델 로딩 중...")
model = torch.hub.load('./yolov5', 'custom', path='best.pt', source='local')
model.conf = 0.5  # 감지 신뢰도 임계값 (0.5 = 50%)
print("모델 로딩 완료!")

# 카메라 초기화
cap = cv2.VideoCapture(0)  # 0 = 기본 카메라
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("카메라를 열 수 없습니다!")
    exit()

print("칼 감지 시스템 시작...")
print("종료하려면 'q'를 누르세요.")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("프레임을 읽을 수 없습니다!")
            break

        # YOLOv5로 감지
        results = model(frame)
        
        # 감지된 객체 확인
        detections = results.pandas().xyxy[0]  # pandas DataFrame으로 결과 가져오기
        knife_detected = len(detections[detections['name'] == 'knife']) > 0
        
        if knife_detected:
            # 칼 감지됨 - LED 켜고 부저 울림
            GPIO.output(LED_PIN, GPIO.HIGH)
            GPIO.output(BUZZER_PIN, GPIO.HIGH)
            print("⚠️  칼 감지!")
        else:
            # 칼 없음 - LED/부저 끔
            GPIO.output(LED_PIN, GPIO.LOW)
            GPIO.output(BUZZER_PIN, GPIO.LOW)
        
        # 결과 화면에 표시 (선택사항)
        annotated_frame = results.render()[0]
        cv2.imshow('Knife Detection', annotated_frame)
        
        # 'q' 키로 종료
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("\n프로그램 종료 중...")

finally:
    # 정리
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
    GPIO.cleanup()
    cap.release()
    cv2.destroyAllWindows()
    print("종료 완료")
