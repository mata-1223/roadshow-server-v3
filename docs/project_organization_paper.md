## 1. **초개인화 Context 요약**

* **초개인화**
  * 고객의 기본 속성·이용 패턴·실시간 행동·상황 정보를 통합 분석하여, **동일 고객이라도 Context(시점·상황·목적)에 따라 최적의 경험(Action)을 제공**하는 것
  * **개인화 + “실시간” + “컨텍스트” → “Action”**
    * 개인화: 고객의 인구통계학적 정보와 과거 구매 이력 같은 축적된 데이터를 바탕으로 유사한 성향의 그룹이나 개인에게 최적화된 경험을 제공하는 것
* **초개인화 Context**
  * 고객의 상황(Who·Where·When)과 행동(What) 데이터를 실시간으로 수집·통합하고, 이를 기반으로 의도(Why)를 추론한 맥락 데이터

**초개인화 Context = (Who + Where + When)상황 x What행동 x Why의도**

'+' : 초개인화를 위한 기초 데이터 자산의 확보

'x' : 확보된 상황 자산에 행동(What)과 추론된 의도(Why)를 결합하여 실행 가능한 비즈니스로 전환

* **Who (고객 속성)** : 행동의 전제가 되는 고객의 고정적·상태적 속성으로, 성별, 연령, 가입 요금제, 단말기 종류 등 행동 발생 직전의 배경이 되는 고객 상태
* **Where (물리적/기술적 환경):** 행동이 발생하는 물리적 공간이나 네트워크 환경으로, 특정 상권, 랜드마크 등의 위치 정보뿐만 아니라 네트워크 품질(음영 지역 등)과 같은 기술적 환경을 포함
* **When (시간적 배경)** : 행동이 발생하는 시점의 시간적 배경으로, 시간대, 계절, 평일/주말 여부 등을 의미
* **What (고객 행동)** : 환경적 상황 위에서 발생하는 고객의 구체적인 움직임으로, 특정 앱의 실행 및 종료, 결제, 검색어 입력 등 실시간으로 발생하는 행동 로그를 의미
* **Why (추론된 의도)** : 상황(Who·Where·When)과 행동(What)을 결합하여 고객이 해당 행동을 수행한 근본적인 목적이나 원인을 추론한 결과
* **초개인화 Context 활용 시나리오 예시**
  * 상담, VOC, 품질, 장애 등의 데이터를 기반으로 고객  **CS Context** (불만·문의·처리 등)를 사전 파악 및 대응
  * 마이K 내 클릭, 탐색, 검색, 체류 행동을 기반으로 고객의  **앱 사용 Context** (요금, 데이터, 혜택, 구매 등)를 파악하여 적합한 액션 수행
  * 고객의 앱/웹 접속 로그(URL, 도메인, 시간대 등)를 기반으로  **SGI Context** (관심사·생활 패턴·상황 변화 등)를 동적으로 파악하고 대응
    * 여행 준비 Intent, Gaming Heavy User Intent, OTT 집중 사용 Intent, 시간대 기반 Dynamic Intent
* **초개인화 Context Engine Mock-up**
  * [https://ktspace.atlassian.net/wiki/spaces/AIServiceLab/pages/787683244](https://ktspace.atlassian.net/wiki/spaces/AIServiceLab/pages/787683244)

## 2. **초개인화 Context Engine 설계**

초개인화 Context Engine은 고객의 배치·실시간 데이터를 Context Feature로 구조화하고, Intent Taxonomy 기반으로 고객 의도를 추론·랭킹하여, 서비스·CRM·Agent 등이 활용 가능한 Context Library를 제공하는 엔진

### [0] Intent Taxonomy

* 고객 행동과 서비스 목적을 기준으로 고객 의도 체계를 표준화하는 기준 영역
* [https://ktspace.atlassian.net/wiki/spaces/AIServiceLab/pages/784375285](https://ktspace.atlassian.net/wiki/spaces/AIServiceLab/pages/784375285)
* Intent Hierarchy, Intent Metadate, Core Feature, Intent 추론 방법론으로 구성
* 예시) CS Intent Taxonomy, 마이K Intent Taxonomy, SGI Intent Taxonomy
* Intent Taxonomy Schema

| **컬럼명**    | **설명**                                | **예시**                             |
| ------------------- | --------------------------------------------- | ------------------------------------------ |
| intent_taxonomy_id  | Intent 체계(분류 체계) 자체 식별자            | TAX-CS-001                                 |
| intent_id           | Intent를 식별하는 고유 ID                     | INT-CS-5120                                |
| intent_nm_ko        | Intent 한글명                                 | WiFi 문제 해결                             |
| intent_nm_en        | Intent 영문명                                 | WiFi Issue Resolution                      |
| L0                  | 최상위 Intent 대분류                          | CS                                         |
| L1                  | 1차 하위 분류                                 | 장애 해결                                  |
| L2                  | 2차 하위 분류                                 | WiFi 장애                                  |
| L3                  | 최종 세부 Intent                              | WiFi 연결 불안정                           |
| inference_type      | Intent 추론 방식                              | Rule , Predictive , Vector                 |
| core_features       | 해당 Intent 추론에 사용되는 핵심 Feature 목록 | wifi_issue_query, speedtest_execute_cnt_1h |
| sequence_required   | 행동 순서/흐름 기반 추론 필요 여부            | Y, N                                       |
| real_time_available | 실시간 데이터 기반 추론 가능 여부             | Y, N                                       |
| ttl_policy          | 해당 Intent가 유효한 시간 정책                | 10m, 1h, 24h, 7d                           |

### [1] Contextual Feature Foundation Layer

* 고객의 배치 데이터와 실시간 데이터를 기반으로 의도 추론에 필요한 Contextual Feature Sets를 생성하는 영역
* [https://ktspace.atlassian.net/wiki/pages/resumedraft.action?draftId=784874879](https://ktspace.atlassian.net/wiki/pages/resumedraft.action?draftId=784874879)

| 모듈                                         | 설명                                              | Input                                                                 | Flow                           | Output (Contextual Feature Sets) |
| -------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------ | -------------------------------- |
| Preprocessing                                | 원천 데이터 정제, 표준화, 유효성 검증             | Batch Data : KFM, SGI, 요금, 납부, 이용량, 장애, 상담, 앱/단말 데이터 |                                |                                  |
| Real-time Data : 실시간 행동 로그            | Data Cleansing, Standardization, Validation       | Preprocessed Batch Data                                               |                                |                                  |
| Preprocessed Real-time Data                  |                                                   |                                                                       |                                |                                  |
| **[1a] Batch Context Feature Builder** | 고객의 장기·중기 상태 기반 피처 생성             | Preprocessed Batch Data                                               | Feature/Index/Score Logic      | Batch Feature Table              |
| **[1b] Event Feature Extractor**       | 실시간 행동 로그에서 즉시성 이벤트 피처 추출      | Preprocessed Real-time Data                                           | Trigger Event Logic            | Event Feature Table              |
| **[1c] Behavioral Pattern Extractor**  | 반복 행동, 탐색 흐름, 관심 변화 등 행동 패턴 분석 | Preprocessed Real-time Data                                           | Window-based Aggregation Logic | Behavior Pattern Feature Table   |

### [2] Intent Inference Layer

* Contextual Feature Sets와 Intent Taxonomy를 기반으로 고객별 Intent를 추론하고, 우선순위화하는 영역 → Context-aware Intent Score
* [https://ktspace.atlassian.net/wiki/x/PozULg](https://ktspace.atlassian.net/wiki/x/PozULg)

| 모듈                                       | 설명                                       | Input                                    | Flow                             | Output                               |
| ------------------------------------------ | ------------------------------------------ | ---------------------------------------- | -------------------------------- | ------------------------------------ |
| **[2a] Rule-Based Intent Trigger**   | 명확한 조건 기반 인텐트 탐지               | Contextual Feature Sets, Intent Taxonomy | Rule & Logic                     | Customer Intent Score                |
| **[2b] Predictive Intent Model**     | 예측 모델 기반 인텐트 가능성 산출          | Contextual Feature Sets, Intent Taxonomy | Inference Model                  | Customer Intent Score                |
| **[2c] Vector Intent Model**         | 고객 Context와 Intent 간 유사도 기반 추론  | Contextual Feature Sets, Intent Taxonomy | Embedding Model, Distance Metric | Customer Intent Score                |
| **[2d] Intent Calibrator**           | Rule/Model/Vector 결과를 통합·보정        | Customer Intent Score                    | Score Calibration                | Calibrated Intent Score              |
| **[2e] Intent Candidate Generator**  | 서비스 활용 가능성이 높은 후보 인텐트 선별 | Calibrated Intent Score                  | Candidate Selection Logic        | Candidate Intent Score               |
| **[2f] Context-aware Intent Ranker** | 최종 인텐트 우선순위 산정                  | Candidate Intent Score                   | Context-aware Ranking            | **Context-aware Intent Score** |

### [3] Context Serving Layer

* 추론된 고객 Intent와 해당 Intent를 설명하는 Core Feautre를 고객 Context 자산으로 구조화하고, 품질·정합성·최신성·활용 현황을 관리하는 영역
* [https://ktspace.atlassian.net/wiki/spaces/AIServiceLab/pages/786792523](https://ktspace.atlassian.net/wiki/spaces/AIServiceLab/pages/786792523)

| 모듈                           | 설명                                                        | Input                                                                | Flow                                                                                    | Output                    |
| ------------------------------ | ----------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------- |
| **[3a] Context Library** | 고객별 Context를 표준 데이터 자산으로 구성                  | Contextual Feature Sets, Context-aware Intent Score, Intent Taxonomy | Context 데이터 구조화, Intent Core Feature Value 구성, Context 유형화                   | Customer Context          |
| **[3b] Context Manager** | Context 자산의 품질, 정합성, 최신성, 활용 현황을 관리·감독 | Customer Context, 생성/변경/활용 로그                                | Quality Check, Consistency Check, Freshness Monitoring, Usage Monitoring, TTL Manage 등 | Context Management Status |
| (eg. Dashboard)                |                                                             |                                                                      |                                                                                         |                           |
