---
title: Roadshow Server V3
emoji: 🎯
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: 초개인화 Context Engine 백엔드 (마이K Intent 116개)
---

# roadshow-server-v3 — Hugging Face Spaces

AX Tech Connect 시연용 백엔드 (FastAPI + DuckDB + MLflow + sklearn).

## 엔드포인트

- `GET /health` — 상태 확인
- `GET /api/scenarios/cs-myk-v3` — 시나리오 메타
- `POST /api/sessions` — 세션 생성
- `POST /api/sessions/{id}/survey` — 설문 제출 → 116개 Intent 추론
- `GET /api/intents/latest?session_id=...` — 최신 Intent Top-N
- `GET /api/admin/tables` — 모든 user 테이블 목록
- `WS /ws` — WebSocket (BEHAVIOR → INTENT_UPDATE)

## 환경 변수 (Space Settings → Variables)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `SCENARIO_ID` | `cs-myk-v3` | 시나리오 ID |
| `TOP_N_INTENT` | `5` | 화면 노출 Top-N |
| `CORS_ORIGINS` | `""` (전체 허용) | 프론트 도메인 화이트리스트 |
| `DB_PATH` | `/data/roadshow_v3.duckdb` | DuckDB 파일 (Dockerfile에서 설정) |
| `MLFLOW_URI` | `sqlite:////data/mlflow_v3.db` | MLflow Tracking |
| `MLFLOW_ARTIFACT_ROOT` | `/data/mlruns_v3` | MLflow 아티팩트 |

## 빌드/실행 (Spaces 자동)

`Dockerfile`로 정의된 컨테이너가 자동 빌드되어 포트 7860에서 실행됩니다.
첫 추론 호출 시 16개 sklearn 모델이 자동 학습 + MLflow 등록됩니다.

## 휘발성 데이터

`/data` 볼륨은 Space 재시작 시 휘발됩니다. 시연용으로는 무방.
영구 보존 필요 시 HF Persistent Storage (유료) 활성화 검토.
