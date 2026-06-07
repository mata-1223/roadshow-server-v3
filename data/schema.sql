-- ────────────────────────────────────────────────────────────
-- roadshow-server-v3 DuckDB Schema
-- 시나리오: cs-myk-v3
-- ────────────────────────────────────────────────────────────

-- 시나리오 메타
CREATE TABLE IF NOT EXISTS scenarios (
    id           VARCHAR PRIMARY KEY,
    name         VARCHAR NOT NULL,
    version      VARCHAR NOT NULL,
    description  TEXT
);

-- Intent 카탈로그 (116개)
CREATE TABLE IF NOT EXISTS catalog_intents (
    intent_id        VARCHAR PRIMARY KEY,
    intent_name      VARCHAR NOT NULL,
    L1_id            VARCHAR NOT NULL,
    L1_name          VARCHAR NOT NULL,
    L2_id            VARCHAR NOT NULL,
    L2_name          VARCHAR NOT NULL,
    inference_type   VARCHAR NOT NULL,    -- 'Rule' | 'Model'
    features_json    VARCHAR              -- JSON array
);

-- Action 카탈로그
CREATE TABLE IF NOT EXISTS catalog_actions (
    action_id        VARCHAR PRIMARY KEY,
    action_name      VARCHAR NOT NULL,
    intents_json     VARCHAR NOT NULL,
    condition        VARCHAR,
    channel          VARCHAR NOT NULL,
    message          VARCHAR
);

-- Behavior 카탈로그
CREATE TABLE IF NOT EXISTS catalog_behaviors (
    behavior_id      VARCHAR PRIMARY KEY,
    step             INTEGER NOT NULL,
    behavior_name    VARCHAR NOT NULL,
    event_type       VARCHAR NOT NULL,
    entity           VARCHAR NOT NULL
);

-- ────────────────────────────────────────────────────────────
-- 시연 런타임 테이블
-- ────────────────────────────────────────────────────────────

-- 시연 세션
CREATE SEQUENCE IF NOT EXISTS seq_sessions;
CREATE TABLE IF NOT EXISTS sessions (
    id               VARCHAR PRIMARY KEY,
    scenario_id      VARCHAR NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stage            VARCHAR DEFAULT 'initial'
);

-- 설문 답변
CREATE SEQUENCE IF NOT EXISTS seq_survey_answers;
CREATE TABLE IF NOT EXISTS survey_answers (
    id               BIGINT DEFAULT nextval('seq_survey_answers') PRIMARY KEY,
    session_id       VARCHAR NOT NULL,
    question_id      VARCHAR NOT NULL,
    answer_code      VARCHAR NOT NULL,
    submitted_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 행동 로그
CREATE SEQUENCE IF NOT EXISTS seq_event_log;
CREATE TABLE IF NOT EXISTS event_log (
    id               BIGINT DEFAULT nextval('seq_event_log') PRIMARY KEY,
    session_id       VARCHAR NOT NULL,
    scenario_id      VARCHAR NOT NULL,
    step             INTEGER,
    behavior_id      VARCHAR,
    event_type       VARCHAR NOT NULL,
    entity           VARCHAR NOT NULL,
    occurred_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Intent Score (단일 추론 시점)
-- baseline_score : 행동 없이 Batch Feature만으로 재추론한 점수
-- final_score    : Batch + Behavioral Pattern Feature 합쳐 재추론한 점수
-- delta_score    : final - baseline (행동이 만든 변화량)
-- rank_change    : baseline_rank - rank (양수면 행동으로 순위 상승)
CREATE SEQUENCE IF NOT EXISTS seq_intent_scores;
CREATE TABLE IF NOT EXISTS intent_scores (
    id               BIGINT DEFAULT nextval('seq_intent_scores') PRIMARY KEY,
    session_id       VARCHAR NOT NULL,
    stage            VARCHAR NOT NULL,    -- 'initial' | 'step_1' | 'step_2' | 'step_3'
    intent_id        VARCHAR NOT NULL,
    baseline_score   DOUBLE NOT NULL,
    final_score      DOUBLE NOT NULL,
    delta_score      DOUBLE DEFAULT 0.0,
    baseline_rank    INTEGER,
    rank             INTEGER,
    rank_change      INTEGER DEFAULT 0,
    inference_type   VARCHAR NOT NULL,
    computed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customer Context (적재 단위: 추론 1회당 1행, 116 Intent 포함된 JSON)
CREATE SEQUENCE IF NOT EXISTS seq_customer_contexts;
CREATE TABLE IF NOT EXISTS customer_contexts (
    id               BIGINT DEFAULT nextval('seq_customer_contexts') PRIMARY KEY,
    session_id       VARCHAR NOT NULL,
    scenario_id      VARCHAR NOT NULL,
    stage            VARCHAR NOT NULL,
    context_json     VARCHAR NOT NULL,    -- Customer Context JSON (Section 4.1 스키마)
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ────────────────────────────────────────────────────────────
-- 인덱스
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_event_log_session  ON event_log (session_id);
CREATE INDEX IF NOT EXISTS idx_intent_scores_session ON intent_scores (session_id, stage);
CREATE INDEX IF NOT EXISTS idx_customer_contexts_session ON customer_contexts (session_id, stage);
