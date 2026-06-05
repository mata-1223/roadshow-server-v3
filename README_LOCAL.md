# roadshow-server-v3

> AX Tech Connect 시연용 백엔드 (마이K Intent Taxonomy 116개 기반)
> 시나리오 ID: `cs-myk-v3`

## 개요

7/7 AX Tech Connect 시연을 위한 **초개인화 Context Engine** 백엔드.

- **시연 컨셉**: 설문 답변과 앱 행동이 116개 Intent 중 의미 있는 분포를 만든다 (페르소나 없음)
- **3-Layer 구조**:
  - [1] Contextual Feature Foundation Layer — Batch Builder + Behavioral Pattern Extractor
  - [2] Intent Inference Layer — Rule (~100) + Model (16) + MLflow 등록
  - [3] Context Serving Layer — Customer Context JSON DB 적재

## 실행

```bash
# 의존성 설치
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 환경 변수
cp .env.example .env

# 서버 실행
uvicorn main:app --reload --port 3002

# MLflow UI (선택)
mlflow ui --backend-store-uri sqlite:///mlflow_v3.db --port 5002
```

## 디렉토리 구조

```
roadshow-server-v3/
├── main.py                ← FastAPI 엔트리
├── config.py              ← 설정 (Pydantic Settings)
├── requirements.txt
├── .env / .env.example
├── core/                  ← 비즈니스 로직
│   ├── inference.py       ← Intent 추론 통합 (Rule + Model)
│   ├── builder.py         ← Batch Context Feature Builder
│   ├── extractor.py       ← Behavioral Pattern Extractor
│   └── ranker.py          ← Top-N Re-ranking
├── data/
│   ├── executor.py        ← DuckDB 실행기
│   ├── schema.sql         ← 테이블 스키마
│   └── seed.py            ← 초기 시드 (Intent 카탈로그 적재)
├── models/                ← ML 모델
│   ├── sklearn_model.py   ← sklearn Pipeline + MLflow 등록
│   └── rule_model.py      ← Rule 기반 추론
├── routes/                ← REST API
│   ├── scenarios.py
│   ├── sessions.py
│   └── intents.py
├── ws/                    ← WebSocket
│   ├── handler.py
│   └── manager.py
└── scenarios/
    └── cs-myk-v3/
        ├── intents.json   ← 116개 Intent 카탈로그
        ├── survey.json    ← 12문항 설문
        ├── feature_map.json   ← 답변 → Base Feature 매핑
        └── actions.json   ← Action 카탈로그
```

## 시연 흐름

1. 참여자가 `/api/scenarios/cs-myk-v3` 메타 로드
2. `POST /api/sessions` 로 세션 생성
3. `POST /api/sessions/{id}/survey` 로 설문 답변 제출
   → Batch Feature 생성 → 116개 Intent Score 추론 → Top-N 반환
4. WebSocket `/ws` 연결
   → 매 행동마다 BEHAVIOR 메시지 송신
   → 서버가 재추론 + INTENT_UPDATE Push
5. 모든 추론 결과는 `customer_contexts` 테이블에 JSON으로 적재

## 시연 명령어 요약

```bash
# 1. 초기화 (필요 시)
rm -f roadshow_v3.duckdb mlflow_v3.db
rm -rf mlruns_v3/

# 2. 서버 시작
uvicorn main:app --reload --port 3002

# 3. 모델 초기 학습 (별도 스크립트, 추후)
# python scripts/train_all_models.py
```
