## 0. 시나리오 개요

### 시연 컨셉

**"설문 답변과 앱/서비스 Trigger 이벤트가 추론될 Intent 분포의 차이를 만든다"**

방문자의 설문 문항 답변을 통해 고객의 장기/중기 배치 특성을 확보하고, MyKT 앱과 서비스 이용 중 발생한 Trigger 이벤트를 실시간으로 반영하여 Intent 분포 변화를 확인한다.

이 문서는 코드 구현 상태를 맞추기 위한 문서가 아니라, CS Intent 추론을 논리적으로 설명하기 위한 기준 문서다. 문서의 Feature 체계와 추론 논리가 확정된 뒤에 `scenarios/cs-myk-v3/intents.json`, Feature Builder/Extractor, Rule/Model 구현을 이 기준에 맞춰 수정한다.

---

## 1. Intent Taxonomy

### 1.1. Intent 규모

| 구분             | 개수                      |
| ---------------- | ------------------------- |
| 전체 Intent (L3) | 113개                     |
| L1 카테고리      | 7개 (INT-1000 ~ INT-7000) |

### 1.2. Intent Metadata 설계 원칙

각 L3 Intent는 아래 세 종류의 Feature와 추론 방법론을 가진다.

| Feature 구분               | 정의                                                                               | 사용 원칙                                                                                                     |
| -------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Batch Feature              | 설문 답변과 KFM/SGI에서 얻는 고객 상태, 이용 성향, 과거 이력, 파생 Index/Score     | 모든 Intent는 최소 1개 이상의 Batch Feature를 가진다.                                                         |
| Event Feature              | 최근 단일 Trigger 이벤트가 직접 의미하는 즉시 신호                                 | 현재 Step1/Step2 선택지만으로 직접 생성되는 결제 재시도, 속도측정 실행, 고객지원 진입/연결 신호에만 사용한다. |
| Behavioral Pattern Feature | 일정 시간 내 반복, 재시도, 순서, 체류, 재조회처럼 누적 행동에서 의미가 생기는 신호 | 단일 이벤트가 아니라 반복/흐름/강도를 설명할 때 사용한다.                                                     |

| 방법론                    | 적용 기준                                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Rule-Based Intent Trigger | 특정 상태, 자격, Step1/Step2 직접 Trigger 자체가 Intent를 강하게 의미하는 경우                             |
| Predictive Intent Model   | Batch + Event + Behavioral Feature 조합으로 관심도, 가능성, 위험도, 선호도를 확률적으로 추정해야 하는 경우 |

### 1.3. 전체 113개 Intent 적용 원칙

113개 Intent를 모두 같은 깊이로 시연하지 않는다. 시연 핵심 Intent는 상세 Feature와 방법론을 정의하고, 나머지 Intent는 L1/L2별 공통 원칙에 따라 관리한다.

| L1             | Feature 설계 원칙                                                                        | 비시연 Intent 처리                                                                         |
| -------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| My 정보 조회   | 가입/청구/사용/혜택 상태 Batch Feature와 조회성 Step1/Step2 행동을 결합한다.             | 직접 Event가 없으면 고객 상태와 행동 Pattern 기반 관심도로 유지한다.                       |
| 상품 탐색/가입 | 사용 강도, 요금 민감도, 단말/로밍/결합 의향 Score와 상품 탐색/신청 행동을 결합한다.      | 상품별 세부 Intent는 같은 L2 공통 Feature를 공유하고, 실제 행동 발생 시 세분화한다.        |
| 셀프처리       | 결제 재시도, 즉시 납부, 자동납부 설정, 요금제 변경 같은 실행 행동이 중요하다.            | 문서/인증/설치 같은 저활성 Intent는 현재 Step1/Step2 직접 신호가 없으면 baseline으로 둔다. |
| 혜택/프로모션  | 비용 부담도, 멤버십 활용도, 탐색 성향, 혜택/쿠폰 Step1/Step2 행동을 결합한다.            | 특정 혜택 카테고리는 탐색 성향과 혜택 행동 기반으로 관리한다.                              |
| 문제 해결/상담 | 속도측정 실행, 챗봇 진입, 전화 상담 연결과 진단/상담 Pattern을 우선한다.                 | 문제 원인이 특정되지 않으면 고객지원/상담 Intent로 먼저 수렴한다.                          |
| 관계/공유      | 가족 회선 수, 결합 형태, 가족결합 Step1/Step2 행동을 결합한다.                           | 그룹/법인 등 비개인 시연 Intent는 별도 B2B context 없이는 baseline으로 둔다.               |
| 이탈/전환      | 이탈 위험 Score, 비용 부담도, 품질 불만 Score와 위약금/해지 Step1/Step2 행동을 결합한다. | 명시적 이탈 Event가 없으면 비용 절감/혜택 최적화 Intent로 완충한다.                        |

---

## 2. Batch Feature 설계

### 2.1. 설문 문항

13문항을 유지한다. 시연 피로도를 낮추기 위해 문항을 추가하지 않고, 부족한 설명력은 파생 Index/Score로 보완한다.

| 설문 번호 | 구분      | 질문                                                        | 답변                                                         |
| --------- | --------- | ----------------------------------------------------------- | ------------------------------------------------------------ |
| Q1        | 고객 상태 | 연령대가 어떻게 되시나요?                                   | 20대 / 30대 / 40대 / 50대 / 60대 이상                        |
| Q2        | 고객 상태 | KT를 얼마나 오래 사용하셨나요?                              | 1년 미만 / 1~3년 / 3~5년 / 5년 이상                         |
| Q3        | 고객 상태 | 현재 사용 중인 월 요금제 금액은?                            | 10만원 이상 / 7~9만원 / 5~6만원 / 3~4만원 / 알릴 수 없음    |
| Q4        | 고객 상태 | 결합 상품 가입 형태는?                                      | 결합 안 함 / 모바일 결합만 / 인터넷+IPTV 결합 / 풀 결합      |
| Q5        | 고객 상태 | 가족 결합 회선 수는?                                        | 1회선 / 2~3회선 / 4회선 이상                                 |
| Q6        | 사용 행동 | 평소 스마트폰을 주로 어떻게 쓰시나요?                       | 영상·게임·SNS / 전화·문자 / 앱 결제·콘텐츠 구독 / 업무용 |
| Q7        | 사용 행동 | 데이터 사용 정도는?                                         | 충분 / 가끔 부족 / 매달 부족                                 |
| Q8        | 행동 이력 | 최근 6개월간 요금이 평소보다 크게 늘어난 경험이 있으신가요? | 없음 / 1~2회 / 3회 이상                                      |
| Q9        | 행동 이력 | 최근 3개월간 통화 품질·속도 관련 고객센터 문의 횟수는?     | 없음 / 1~2회 / 3회 이상                                      |
| Q10       | 행동 이력 | 최근 1주간 멤버십 혜택을 사용한 횟수는?                     | 사용 안 함 / 1~2회 / 3회 이상                                |
| Q11       | 행동 이력 | 최근 1주간 OTT 콘텐츠를 시청한 빈도는?                      | 매일 / 주 2~4회 / 월 1~3회 / 거의 안 봄                     |
| Q12       | 사용 맥락 | 현재 단말기 사용 기간은?                                    | 1년 미만 / 1~2년 / 2~3년 / 3년 이상                         |
| Q13       | 사용 맥락 | 최근 1년 해외 방문 빈도는?                                  | 없음 / 1~2회 / 3회 이상                                      |

### 2.2. Base Feature

Base Feature는 Batch Feature의 가장 낮은 단계다. 설문 문항과 1:1로 매칭되는 값뿐 아니라, 복잡한 정규화 없이 사칙연산으로 생성되는 Delta Feature와 Ratio Feature도 Base Feature에 포함한다. Feature Type은 `base`, `delta`, `ratio`로 구분한다.

| Feature Type | Feature 한글          | Feature 영어                    | 가질 수 있는 값                                       | 데이터 타입 | 설문 매칭/생성 로직                                                                                                                                                                            | 의미                        |
| ------------ | --------------------- | ------------------------------- | ----------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| base         | 나이                  | `age`                         | 25 / 35 / 45 / 55 / 65                                | integer     | Q1: 20대=25, 30대=35, 40대=45, 50대=55, 60대 이상=65                                                                                                                                           | 인구통계 및 상담 대응 방식  |
| base         | 가입 개월 수          | `tenure_months`               | 6 / 24 / 48 / 84                                      | integer     | Q2: 1년 미만=6, 1~3년=24, 3~5년=48, 5년 이상=84                                                                                                                                                | 장기 고객성, 약정/이탈 판단 |
| base         | 요금제 월정액         | `monthly_fee`                 | 35000 / 55000 / 80000 / 100000                        | integer     | Q3: 10만원 이상=100000, 7~9만원=80000, 5~6만원=55000, 3~4만원=35000, 알릴 수 없음=55000                                                                                                        | 비용 부담, 업셀/다운셀 판단 |
| base         | 요금제 구간           | `plan_tier`                   | premium / mid / standard / lite / unknown             | string      | Q3: 10만원 이상=premium, 7~9만원=mid, 5~6만원=standard, 3~4만원=lite, 알릴 수 없음=unknown                                                                                                     | 요금제 수준 라벨            |
| base         | 결합 여부             | `bundle_yn`                   | true / false                                          | boolean     | Q4: 결합 안 함=false, 그 외=true                                                                                                                                                               | 결합/홈상품 context         |
| base         | 결합 형태             | `bundle_type`                 | none / mobile_only / home / full                      | string      | Q4: 결합 안 함=none, 모바일 결합만=mobile_only, 인터넷+IPTV 결합=home, 풀 결합=full                                                                                                            | 결합 강도                   |
| base         | 가족 회선 수          | `family_line_count`           | 1 / 3 / 5                                             | integer     | Q5: 1회선=1, 2~3회선=3, 4회선 이상=5                                                                                                                                                           | 가족결합/공유 판단          |
| base         | 사용 패턴             | `usage_pattern`               | data_heavy / voice_heavy / content_heavy / work_heavy | string      | Q6: 영상·게임·SNS=data_heavy, 전화·문자=voice_heavy, 앱 결제·콘텐츠 구독=content_heavy, 업무용=work_heavy                                                                                  | 사용 성향                   |
| ratio        | 데이터 사용률         | `data_usage_rate`             | 0.40 / 0.70 / 0.90                                    | float       | Q7: 충분=0.40, 가끔 부족=0.70, 매달 부족=0.90                                                                                                                                                  | 데이터 부족 판단            |
| ratio        | 잔여 데이터 비율      | `remaining_data_ratio`        | 0.60 / 0.30 / 0.10                                    | float       | Q7: 충분=0.60, 가끔 부족=0.30, 매달 부족=0.10                                                                                                                                                  | 데이터 충전/공유 필요성     |
| base         | 청구 급증 경험 6m     | `bill_shock_count_6m`         | 0 / 1 / 3                                             | integer     | Q8: 없음=0, 1~2회=1, 3회 이상=3                                                                                                                                                                | 청구 변동, 비용 부담        |
| base         | 품질 CS 문의 3m       | `quality_cs_count_3m`         | 0 / 1 / 3                                             | integer     | Q9: 없음=0, 1~2회=1, 3회 이상=3                                                                                                                                                                | 품질 불만, 상담 필요성      |
| base         | 멤버십 주간 사용 횟수 | `membership_use_count_weekly` | 0 / 1 / 3                                             | integer     | Q10: 사용 안 함=0, 1~2회=1, 3회 이상=3                                                                                                                                                         | 혜택 활용 적극성            |
| ratio        | OTT 사용 빈도         | `ott_usage_frequency`         | 0.85 / 0.50 / 0.20 / 0.05                             | float       | Q11: 매일=0.85, 주 2~4회=0.50, 월 1~3회=0.20, 거의 안 봄=0.05                                                                                                                                  | 콘텐츠 수요, 추천 수용도    |
| base         | 단말 사용 기간        | `device_age_months`           | 6 / 18 / 30 / 48                                      | integer     | Q12: 1년 미만=6, 1~2년=18, 2~3년=30, 3년 이상=48                                                                                                                                               | 단말 교체 가능성            |
| base         | 로밍 이력             | `roaming_history_count_1y`    | 0 / 1 / 3                                             | integer     | Q13: 없음=0, 1~2회=1, 3회 이상=3                                                                                                                                                               | 로밍 이용 이력              |
| base         | 해외 출국 빈도        | `overseas_trip_count_1y`      | 0 / 1 / 3                                             | integer     | Q13: 없음=0, 1~2회=1, 3회 이상=3                                                                                                                                                               | 로밍 context                |
| ratio        | 약정 진행률           | `contract_progress_rate`      | 0.25 / 1.00                                           | float       | Q2에서 생성된 `tenure_months`로 `min(tenure_months / 24, 1.0)` 계산                                                                                                                        | 약정 후반부 판단            |
| ratio        | 30일 상담 횟수        | `support_contact_count_30d`   | 0.0 / 0.3 / 1.0                                       | float       | Q9에서 생성된 `quality_cs_count_3m`으로 `round(quality_cs_count_3m / 3, 1)` 계산                                                                                                           | 30일 단위 상담 빈도 proxy   |
| delta        | 청구 증감률           | `bill_delta_rate`             | 0.00 / 0.08 / 0.18                                    | float       | Q8에서 생성된 `bill_shock_count_6m` 기준: 0이면 0.00, 1이면 0.08, 3이면 0.18. 추후 KFM/SGI 이전 평균 청구액 확보 시 (현재 청구액 - 최근 6개월 평균 청구액) / 최근 6개월 평균 청구액으로 대체 | 청구 변동 체감              |
| delta        | 데이터 사용 증감률    | `data_usage_delta_rate`       | 0.02 / 0.08 / 0.18                                    | float       | Q7에서 생성된 `data_usage_rate` 기준: `>=0.8`이면 0.18, `>=0.6`이면 0.08, 그 외 0.02                                                                                                     | 데이터 사용 증가 추정       |

### 2.3. Index Feature

Index Feature는 Base Feature를 집계하거나 정규화하여 만든 Batch Feature다. 아직 특정 Intent를 예측하는 모델/룰을 적용하지 않은 고객 상태 지표다.

| Index                                              | 의미                              | 사용 Feature                                                                                                            | 생성 수식                                                                                                                                                                                                                                         |
| -------------------------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 비용 부담도 (`cost_burden_score`)                | 통신비 체감 부담                  | 청구 급증 경험 6m (`bill_shock_count_6m`), 요금제 월정액 (`monthly_fee`)                                            | `fee_norm = min(monthly_fee / 100000, 1)`; `shock_norm = min(bill_shock_count_6m / 3, 1)`; `round(0.65 * shock_norm + 0.35 * fee_norm, 4)`                                                                                                  |
| 품질 만족도 (`quality_satisfaction_score`)       | 통화/속도/네트워크 품질 만족 수준 | 품질 CS 문의 3m (`quality_cs_count_3m`)                                                                               | `cs_norm = min(quality_cs_count_3m / 3, 1)`; `max(round(1 - 0.75 * cs_norm, 4), 0.25)`                                                                                                                                                        |
| 멤버십 활용도 (`membership_engagement_score`)    | 혜택 활용 적극성                  | 멤버십 주간 사용 횟수 (`membership_use_count_weekly`)                                                                 | `0.10 if count=0 else 0.45 if count=1 else 0.80`                                                                                                                                                                                                |
| 요금 민감도 Index (`price_sensitivity_index`)    | 가격 민감도                       | 비용 부담도 (`cost_burden_score`), 요금제 월정액 (`monthly_fee`)                                                    | `fee_norm = min(monthly_fee / 100000, 1)`; `round((0.6 * cost_burden_score + 0.4 * fee_norm) * 100, 2)`                                                                                                                                       |
| 고객 가치 Index (`customer_value_index`)         | 유지/추천 우선순위                | 가입 개월 수 (`tenure_months`), 결합 형태 (`bundle_type`), 가족 회선 수 (`family_line_count`)                     | `tenure_norm = min(tenure_months / 84, 1)`; `bundle_weight = none:0, mobile_only:0.4, home:0.7, full:1.0`; `family_norm = min(family_line_count / 5, 1)`; `round((0.4 * tenure_norm + 0.3 * bundle_weight + 0.3 * family_norm) * 100, 2)` |
| 사용 강도 Index (`usage_intensity_index`)        | 활성 이용 강도                    | 데이터 사용률 (`data_usage_rate`), 사용 패턴 (`usage_pattern`), OTT 사용 빈도 (`ott_usage_frequency`)             | `pattern_weight = data_heavy:0.9, content_heavy:0.7, work_heavy:0.5, voice_heavy:0.2`; `round((0.45 * data_usage_rate + 0.35 * pattern_weight + 0.20 * ott_usage_frequency) * 100, 2)`                                                        |
| 탐색 성향 Index (`exploration_propensity_index`) | 신상품/혜택 탐색 가능성           | OTT 사용 빈도 (`ott_usage_frequency`), 멤버십 활용도 (`membership_engagement_score`), 사용 패턴 (`usage_pattern`) | `pattern_weight = content_heavy:0.8, data_heavy:0.7, work_heavy:0.5, voice_heavy:0.3`; `round((0.45 * ott_usage_frequency + 0.35 * membership_engagement_score + 0.20 * pattern_weight) * 100, 2)`                                            |

### 2.4. Score Feature

Score Feature는 Batch Feature의 하위 유형이다. Base Feature와 Index Feature를 입력으로 구체적인 Rule 또는 Model 로직을 적용해 파생한 예측성 Feature이며, Intent 최종 score와는 다르다. Intent 최종 score는 Section 5의 `방법론 상세`에서 Batch Feature, Event Feature, Behavioral Pattern Feature를 조합해 별도로 정의한다.

| Score Feature                                              | 의미                                                               | 사용 Feature                                                                                                                                                                         | 생성 수식                                                                                                                                                                                                                                                                              |
| ---------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 이탈 위험 Score (`churn_risk_score`)                     | 해지/번호이동/비용 절감 가능성을 나타내는 Batch 파생 Score         | 비용 부담도 (`cost_burden_score`), 품질 만족도 (`quality_satisfaction_score`), 가입 개월 수 (`tenure_months`), 청구 급증 경험 6m (`bill_shock_count_6m`)                     | `tenure_risk = 1 - min(tenure_months / 84, 1)`; `shock_norm = min(bill_shock_count_6m / 3, 1)`; `round(0.35 * cost_burden_score + 0.30 * (1 - quality_satisfaction_score) + 0.20 * tenure_risk + 0.15 * shock_norm, 4)`                                                          |
| 추천 적합도 Score (`recommendation_fit_score`)           | AI 추천/개인화 혜택을 받아들일 가능성을 나타내는 Batch 파생 Score  | 고객 가치 Index (`customer_value_index`), 사용 강도 Index (`usage_intensity_index`), OTT 사용 빈도 (`ott_usage_frequency`), 탐색 성향 Index (`exploration_propensity_index`) | `round(0.30 * customer_value_index/100 + 0.30 * usage_intensity_index/100 + 0.20 * ott_usage_frequency + 0.20 * exploration_propensity_index/100, 4)`                                                                                                                                |
| 품질 불만 Score (`quality_complaint_score`)              | 품질 문제/AS/상담 필요 강도를 나타내는 Batch 파생 Score            | 품질 만족도 (`quality_satisfaction_score`), 품질 CS 문의 3m (`quality_cs_count_3m`)                                                                                              | `cs_norm = min(quality_cs_count_3m / 3, 1)`; `round(0.65 * (1 - quality_satisfaction_score) + 0.35 * cs_norm, 4)`                                                                                                                                                                  |
| 결합 확장 Score (`bundle_expansion_score`)               | 가족결합 추가/관리 가능성을 나타내는 Batch 파생 Score              | 결합 형태 (`bundle_type`), 가족 회선 수 (`family_line_count`), 고객 가치 Index (`customer_value_index`)                                                                        | `bundle_weight = none:0, mobile_only:0.4, home:0.7, full:1.0`; `family_norm = min(family_line_count / 5, 1)`; `round(0.35 * bundle_weight + 0.35 * family_norm + 0.30 * customer_value_index/100, 4)`                                                                            |
| 업셀 적합도 Score (`upsell_fit_score`)                   | 상위 요금제/5G/데이터 상품 전환 가능성을 나타내는 Batch 파생 Score | 데이터 사용률 (`data_usage_rate`), 잔여 데이터 비율 (`remaining_data_ratio`), 사용 강도 Index (`usage_intensity_index`), 비용 부담도 (`cost_burden_score`)                   | `data_need = 1 - remaining_data_ratio`; `payment_room = 1 - cost_burden_score`; `round(0.35 * data_usage_rate + 0.25 * data_need + 0.25 * usage_intensity_index/100 + 0.15 * payment_room, 4)`                                                                                   |
| 단말 교체 의향 Score (`device_replacement_intent_score`) | 단말 탐색/구매 가능성을 나타내는 Batch 파생 Score                  | 단말 사용 기간 (`device_age_months`), 약정 진행률 (`contract_progress_rate`), OTT 사용 빈도 (`ott_usage_frequency`), 사용 패턴 (`usage_pattern`)                             | `age_norm = min(device_age_months / 48, 1)`; `pattern_weight = content_heavy:0.75, data_heavy:0.70, work_heavy:0.55, voice_heavy:0.35`; `round(0.40 * age_norm + 0.25 * contract_progress_rate + 0.20 * ott_usage_frequency + 0.15 * pattern_weight, 4)`                         |
| 로밍 의향 Score (`roaming_intent_score`)                 | 로밍 조회/상품 탐색/가입 가능성을 나타내는 Batch 파생 Score        | 로밍 이력 (`roaming_history_count_1y`), 해외 출국 빈도 (`overseas_trip_count_1y`), 사용 패턴 (`usage_pattern`)                                                                 | `roaming_norm = min(roaming_history_count_1y / 3, 1)`; `trip_norm = min(overseas_trip_count_1y / 3, 1)`; `pattern_weight = data_heavy:0.75, content_heavy:0.65, work_heavy:0.60, voice_heavy:0.35`; `round(0.45 * roaming_norm + 0.40 * trip_norm + 0.15 * pattern_weight, 4)` |

### 2.5. Base Intent 추론

* Batch Feature를 활용하여 L3 Intent의 초기 Intent Score 산정
  * Rule 기반 추론은 사전 정의된 조건식을 통해 Score 계산
  * Model 기반 추론은 현재 활용 가능한 Batch Feature만을 입력값으로 사용하여 Score 계산
* 두 방법론을 통해 산정된 Intent Score를 정규화한 후, 최종 Intent Score를 기반으로 **Base Intent Top-K 생성**
* 예시 Output : Customer Intent Score (Top 5 + 기타, 전체 113개 분포)
* Base Intent 단계에서는 Step1/Step2 선택 전이므로 Event Feature와 Behavioral Pattern Feature는 0 또는 미발생으로 간주한다.

> 예시 입력 — 30대 / 5년 이상 가입 / 7~9만원 요금제 / 풀 결합 / 가족 4회선 이상 / 영상·게임·SNS 위주 / 데이터 매달 부족 / 청구 급증 없음 / 품질 CS 없음 / 멤버십 3회 이상 / OTT 매일 / 단말 2~3년 / 해외 방문 없음

주요 Batch 산출값:

| Feature                          | 예시 값 | 해석                                                                                 |
| -------------------------------- | ------- | ------------------------------------------------------------------------------------ |
| `usage_intensity_index`        | 89.00   | 데이터 헤비, 데이터 부족, OTT 매일 이용으로 사용 강도가 높음                         |
| `recommendation_fit_score`     | 0.8975  | 고객 가치, 사용 강도, OTT, 탐색 성향이 모두 높아 추천 수용 가능성이 큼               |
| `upsell_fit_score`             | 0.8705  | 잔여 데이터 부족과 높은 사용 강도로 데이터 상품/상위 요금제 필요도가 큼              |
| `exploration_propensity_index` | 80.25   | 콘텐츠 이용과 멤버십 활용이 높아 혜택/상품 탐색 가능성이 큼                          |
| `price_sensitivity_index`      | 48.80   | 중상위 요금제를 쓰지만 청구 급증 경험은 없어 비용 절감보다 상품 최적화 신호가 우세함 |

| Rank         | Intent ID | L1             | L2               | L3               | Probability      |
| ------------ | --------- | -------------- | ---------------- | ---------------- | ---------------- |
| 1            | INT-4310  | 혜택/프로모션  | 맞춤 추천 탐색   | AI 추천 탐색     | 15.3%            |
| 2            | INT-2130  | 상품 탐색/가입 | 모바일 상품 탐색 | 데이터 상품 탐색 | 14.8%            |
| 3            | INT-2120  | 상품 탐색/가입 | 모바일 상품 탐색 | 5G 상품 탐색     | 13.4%            |
| 4            | INT-4320  | 혜택/프로모션  | 맞춤 추천 탐색   | 개인화 혜택 탐색 | 12.8%            |
| 5            | INT-4330  | 혜택/프로모션  | 맞춤 추천 탐색   | 추천 요금제 검토 | 11.9%            |
| 기타         | -         | 기타           | n = 108          |                  | 31.8%            |
| **합** |           |                |                  |                  | **100.0%** |

> Probability는 **113개 Intent 전체 Score 합**을 분모로 정규화한 분포. Top 5 외 Intent는 "기타"로 묶어 분포 합만 표시한다.

---

## 3. Event Feature 설계

### 3.1. Event Feature 원칙

Event Feature는 raw `page_view`나 `click`을 그대로 쓰지 않는다. 현재 문서에서는 **Step1/Step2 선택지만으로 직접 생성 가능한 Trigger 이벤트**만 Event Feature로 사용한다.

시연 앱 행동 선택지는 마이K 앱에서 고객이 실제로 실행할 수 있는 행동을 2단계 트리 구조로 정의한다. Stage 1은 6개 상위 메뉴 중 1개를 선택하는 단계이고, Stage 2는 선택한 상위 메뉴에 따라 하위 행동 3개와 공통 보조 행동 `BACK`, `EXIT`을 함께 노출하는 단계다.

| Stage   | Action ID | 행동 명                                   |
| ------- | --------- | ----------------------------------------- |
| Stage 1 | `1-A`   | 데이터 사용량 페이지 진입                 |
| Stage 1 | `1-B`   | 요금/청구 상세 페이지 진입                |
| Stage 1 | `1-C`   | 가입정보 페이지 진입 (요금제·약정·해지) |
| Stage 1 | `1-D`   | 혜택/멤버십 페이지 진입                   |
| Stage 1 | `1-E`   | 상품 탐색 페이지 진입                     |
| Stage 1 | `1-F`   | 고객지원 페이지 진입                      |

| Stage 1 선택          | Stage 2 하위 행동 3개                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------------ |
| `1-A` 데이터 사용량 | `2-A1` 데이터 충전 버튼 클릭, `2-A2` 데이터 부가서비스 가입 페이지, `2-A3` 사용 상세 그래프 조회 |
| `1-B` 요금/청구     | `2-B1` 청구 상세 항목 조회, `2-B2` 즉시 납부 버튼 클릭, `2-B3` 자동납부 설정 변경                |
| `1-C` 가입정보      | `2-C1` 요금제 변경 신청 클릭, `2-C2` 위약금 계산 페이지 진입, `2-C3` 해지 신청 페이지 진입       |
| `1-D` 혜택/멤버십   | `2-D1` 쿠폰 사용/혜택 적용 클릭, `2-D2` 멤버십 등급 혜택 조회, `2-D3` 이벤트/프로모션 페이지     |
| `1-E` 상품 탐색     | `2-E1` 요금제 탐색, `2-E2` 단말기 탐색, `2-E3` 가족 결합 회선 추가 페이지                        |
| `1-F` 고객지원      | `2-F1` WiFi 진단 / 속도 측정 실행, `2-F2` 챗봇 상담 진입, `2-F3` 전화 상담 연결 클릭             |

| 공통 행동 ID | 행동 명  | 부가 설명                                                                 |
| ------------ | -------- | ------------------------------------------------------------------------- |
| `BACK`     | 뒤로가기 | Step1 선택 화면으로 복귀하며, 관심사 이동 신호로 적재한다.                |
| `EXIT`     | 앱 이탈  | 세션을 종료하며, Intent 재추론과 Customer Context 갱신은 수행하지 않는다. |

총 행동 수는 Stage 1 6개 + Stage 2 18개 + 공통 보조 행동 2개(`BACK`, `EXIT`) = 26개다.

시연 흐름 예시는 아래와 같다.

| 시연 맥락                      | 선택 흐름                                                                                           |
| ------------------------------ | --------------------------------------------------------------------------------------------------- |
| 데이터 부족 + 상위 요금제 관심 | `1-A` 데이터 사용량 -> `BACK` -> `1-E` 상품 탐색 -> `2-E1` 요금제 탐색                      |
| 품질 불만 -> 상담              | `1-F` 고객지원 -> `2-F1` WiFi 진단 / 속도 측정 실행 -> `BACK` -> `2-F3` 전화 상담 연결 클릭 |

Step1/Step2 선택값은 원천 행동 로그이며, 모든 선택값이 Event Feature가 되지는 않는다. 선택지는 아래 두 단계를 거쳐 Feature로 변환한다.

1. 모든 Step1/Step2 선택지는 Behavioral Pattern Feature 생성을 위한 `behavior_event_type`, `behavior_entity`로 정규화한다.
2. 선택 행동 자체가 즉시 Trigger 의미를 가질 때만 Event Feature를 생성한다.

따라서 `데이터 사용량 페이지 진입`, `청구 상세 항목 조회`, `요금제 탐색`, `위약금 계산 페이지 진입`은 Behavioral Pattern Feature의 원천이지만 Event Feature는 아니다. 반면 `고객지원 페이지 진입`, `즉시 납부 버튼 클릭`, `WiFi 진단 / 속도 측정 실행`, `챗봇 상담 진입`, `전화 상담 연결 클릭`은 선택 행동 자체가 즉시 Trigger 의미를 가지므로 Event Feature를 생성한다.

프로젝트 계획상 `event_type`과 `entity`는 모두 정의되어 있지만, 시연 설명과 Event Feature Output에서는 두 값의 조합으로 확정되는 Trigger Feature명을 `event_type`으로 단순화해 노출한다.

### 3.2. Trigger Event Taxonomy

| 카테고리      | 직접 생성 선택 단계 | 직접 생성 선택지           | event_type         | event_value 데이터 타입 | 의미/활용 목적           |
| ------------- | ------------------- | -------------------------- | ------------------ | ----------------------- | ------------------------ |
| 결제/납부     | Step2               | 즉시 납부 버튼 클릭        | `payment_retry`  | boolean                 | 납부 실행/재시도 의도    |
| 고객지원      | Step1               | 고객지원 페이지 진입       | `support_entry`  | boolean                 | 고객지원 진입            |
| 고객지원      | Step2               | 챗봇 상담 진입             | `support_entry`  | boolean                 | 고객지원 진입            |
| 고객지원      | Step2               | 전화 상담 연결 클릭        | `support_entry`  | boolean                 | 고객지원 진입            |
| 고객지원      | Step2               | 챗봇 상담 진입             | `chatbot_start`  | boolean                 | 챗봇 기반 셀프 상담 진입 |
| 고객지원      | Step2               | 전화 상담 연결 클릭        | `call_cs_click`  | boolean                 | 상담사 연결 의도         |
| 네트워크/품질 | Step2               | WiFi 진단 / 속도 측정 실행 | `speed_test_run` | boolean                 | 품질/속도 문제 확인 의도 |

### 3.3. Event Feature Output 예시

| event_ts | session_id | cust_id | category      | 선택 단계 | 선택지                     | event_type         | event_value |
| -------- | ---------- | ------- | ------------- | --------- | -------------------------- | ------------------ | ----------- |
| 14:30:12 | S001       | A001    | 결제/납부     | Step2     | 즉시 납부 버튼 클릭        | `payment_retry`  | True        |
| 14:31:00 | S001       | A001    | 고객지원      | Step1     | 고객지원 페이지 진입       | `support_entry`  | True        |
| 14:31:03 | S001       | A001    | 고객지원      | Step2     | 전화 상담 연결 클릭        | `support_entry`  | True        |
| 14:31:03 | S001       | A001    | 고객지원      | Step2     | 전화 상담 연결 클릭        | `call_cs_click`  | True        |
| 14:32:45 | S002       | A002    | 네트워크/품질 | Step2     | WiFi 진단 / 속도 측정 실행 | `speed_test_run` | True        |
| 14:33:10 | S003       | A003    | 고객지원      | Step2     | 챗봇 상담 진입             | `support_entry`  | True        |
| 14:33:10 | S003       | A003    | 고객지원      | Step2     | 챗봇 상담 진입             | `chatbot_start`  | True        |

---

## 4. Behavioral Pattern Feature 설계

### 4.1. Behavioral Pattern Extractor 원칙

Behavioral Pattern Extractor는 사용자가 Step1/Step2에서 선택한 Action을 기반으로 생성된 실시간 행동 데이터를 집계하여 Behavioral Pattern Feature를 생성한다. CS 시나리오는 2단계 트리 구조이므로, Step1 상위 메뉴 선택은 관심 영역 진입 신호로, Step2 하위 행동은 구체 행동 신호로 사용한다. raw `click/page_view`가 아니라 **행동 목적(behavior_event_type)** 과 **관심 대상(behavior_entity)** 을 기준으로 반복, 상담 전환, 이탈 전환, 진단 반복, 의사결정 흐름을 aggregation한다.

Step1/Step2 선택값과 Feature 생성은 아래 원칙으로 분리한다.

| 구분                       | 데이터 타입        | 설명                                                                                            |
| -------------------------- | ------------------ | ----------------------------------------------------------------------------------------------- |
| `selected_step`          | string enum        | 선택 단계.`step1`, `step2`, `common` 중 하나                                              |
| `selected_action_id`     | string             | 시연자가 선택한 행동 ID. 예:`1-F`, `2-B2`, `BACK`                                         |
| `parent_action_id`       | string/null        | Step2 선택의 상위 Step1 ID. Step1 또는 공통 행동이면 `null`                                   |
| `selected_action_name`   | string             | 화면에 노출되는 선택지명. 예: 고객지원 페이지 진입, 즉시 납부 버튼 클릭                         |
| `raw_event_type`         | string enum        | `behaviors.json`에 정의된 원천 이벤트 타입. 예: `click`, `page_view`, `support_entry`   |
| `raw_entity`             | string enum        | `behaviors.json`에 정의된 원천 entity. 예: `pay_now_button`                                 |
| `behavior_event_type`    | string enum        | Behavioral Pattern 집계를 위한 정규화 행동 유형                                                 |
| `behavior_entity`        | string enum        | Behavioral Pattern 집계를 위한 정규화 관심 대상                                                 |
| `derived_event_features` | array `<string>` | Step1/Step2 선택지만으로 직접 생성되는 Event Feature 목록. 생성할 Event가 없으면 빈 배열 `[]` |
| `derived_event_value`    | boolean            | Event Feature 값. 발생 시 `True`, 미발생 시 `False`                                         |

즉, Step1/Step2 선택지는 Behavioral Feature의 직접 원천이고, Event Feature는 선택 행동 자체가 Trigger인 경우에만 생성한다. 선택 이후 결과 신호는 현재 문서 범위에서 Event Feature로 사용하지 않는다.

### 4.2. behavior_event_type 정의

`behavior_event_type`은 `string enum` 타입이다. 원천 `raw_event_type`이 `click` 또는 `page_view`라도, 시연 분석에서는 아래 정규화 타입으로 변환해 사용한다.

| behavior_event_type   | 데이터 타입 | 의미                                                                     |
| --------------------- | ----------- | ------------------------------------------------------------------------ |
| `inquiry_action`    | string      | 요금, 사용량, 가입정보, 혜택 등 정보 확인 행동                           |
| `comparison_action` | string      | 요금제, 단말, 프로모션, 데이터 부가상품 등 대안 탐색/비교 행동           |
| `support_action`    | string      | 고객센터 진입, 챗봇 실행, 상담사 연결 클릭                               |
| `decision_action`   | string      | 즉시 납부, 요금제 변경, 쿠폰 적용, 데이터 충전처럼 실행 의도가 있는 행동 |
| `diagnostic_action` | string      | 속도측정, WiFi 진단, 품질 점검 등 원인 확인 행동                         |
| `churn_action`      | string      | 위약금 조회, 해지 신청 페이지 진입처럼 이탈 검토를 의미하는 행동         |
| `navigation_action` | string      | 뒤로가기처럼 탐색 위치를 바꾸지만 Intent 신호가 약한 행동                |
| `exit_action`       | string      | 앱 이탈 또는 세션 종료 행동                                              |

### 4.3. entity 정의

`behavior_entity`는 `string enum` 타입이다. 현재 Step1/Step2 선택지에서 직접 생성되는 entity만 사용한다.

| entity                 | 데이터 타입 | 해당 선택 단계 | 해당 선택지                   |
| ---------------------- | ----------- | -------------- | ----------------------------- |
| `data_usage`         | string      | Step1          | 데이터 사용량 페이지 진입     |
| `billing`            | string      | Step1          | 요금/청구 상세 페이지 진입    |
| `subscription_info`  | string      | Step1          | 가입정보 페이지 진입          |
| `benefit_membership` | string      | Step1          | 혜택/멤버십 페이지 진입       |
| `product_explore`    | string      | Step1          | 상품 탐색 페이지 진입         |
| `customer_support`   | string      | Step1          | 고객지원 페이지 진입          |
| `data_topup`         | string      | Step2          | 데이터 충전 버튼 클릭         |
| `data_addon`         | string      | Step2          | 데이터 부가서비스 가입 페이지 |
| `usage_detail`       | string      | Step2          | 사용 상세 그래프 조회         |
| `billing_detail`     | string      | Step2          | 청구 상세 항목 조회           |
| `payment`            | string      | Step2          | 즉시 납부 버튼 클릭           |
| `autopay`            | string      | Step2          | 자동납부 설정 변경            |
| `plan_change`        | string      | Step2          | 요금제 변경 신청 클릭         |
| `penalty`            | string      | Step2          | 위약금 계산 페이지 진입       |
| `cancel`             | string      | Step2          | 해지 신청 페이지 진입         |
| `coupon`             | string      | Step2          | 쿠폰 사용/혜택 적용 클릭      |
| `membership_benefit` | string      | Step2          | 멤버십 등급 혜택 조회         |
| `promotion_benefit`  | string      | Step2          | 이벤트/프로모션 페이지        |
| `plan_compare`       | string      | Step2          | 요금제 탐색                   |
| `device`             | string      | Step2          | 단말기 탐색                   |
| `family_bundle`      | string      | Step2          | 가족 결합 회선 추가 페이지    |
| `quality_diagnosis`  | string      | Step2          | WiFi 진단 / 속도 측정 실행    |
| `chatbot`            | string      | Step2          | 챗봇 상담 진입                |
| `support_consult`    | string      | Step2          | 전화 상담 연결 클릭           |
| `navigation`         | string      | common         | 뒤로가기                      |
| `session_exit`       | string      | common         | 앱 이탈                       |

### 4.4. Step1/Step2 선택지 기준 Feature 매핑

아래 표는 현재 `scenarios/cs-myk-v3/behaviors.json`의 Step1/Step2 선택지를 기준으로 한다. `derived_event_features`는 `array<string>` 타입이며, 생성할 Event Feature가 없으면 `[]`로 둔다.

| 선택 단계 | Action ID | 상위 Step1 | 선택지                        | raw_event_type / raw_entity (원래 행동로그) | behavior_event_type   | behavior_entity        | derived_event_features                 | Event 값 타입 | 생성 조건                                              |
| --------- | --------- | ---------- | ----------------------------- | ------------------------------------------- | --------------------- | ---------------------- | -------------------------------------- | ------------- | ------------------------------------------------------ |
| Step1     | `1-A`   | -          | 데이터 사용량 페이지 진입     | `page_view` / `data_usage`              | `inquiry_action`    | `data_usage`         | []                                     | nullable      | 상위 관심 영역 진입이므로 Behavioral Feature만 생성    |
| Step1     | `1-B`   | -          | 요금/청구 상세 페이지 진입    | `page_view` / `billing`                 | `inquiry_action`    | `billing`            | []                                     | nullable      | 상위 관심 영역 진입이므로 Behavioral Feature만 생성    |
| Step1     | `1-C`   | -          | 가입정보 페이지 진입          | `page_view` / `subscription_info`       | `inquiry_action`    | `subscription_info`  | []                                     | nullable      | 상위 관심 영역 진입이므로 Behavioral Feature만 생성    |
| Step1     | `1-D`   | -          | 혜택/멤버십 페이지 진입       | `page_view` / `benefit_membership`      | `inquiry_action`    | `benefit_membership` | []                                     | nullable      | 상위 관심 영역 진입이므로 Behavioral Feature만 생성    |
| Step1     | `1-E`   | -          | 상품 탐색 페이지 진입         | `page_view` / `product_explore`         | `comparison_action` | `product_explore`    | []                                     | nullable      | 상품 탐색 상위 진입은 비교/탐색 Behavioral 신호로 처리 |
| Step1     | `1-F`   | -          | 고객지원 페이지 진입          | `page_view` / `customer_support`        | `support_action`    | `customer_support`   | [`support_entry`]                    | boolean       | 고객지원 진입 자체가 Trigger이므로 생성                |
| Step2     | `2-A1`  | `1-A`    | 데이터 충전 버튼 클릭         | `click` / `data_topup_button`           | `decision_action`   | `data_topup`         | []                                     | nullable      | 실행 행동은 Behavioral Feature로만 사용                |
| Step2     | `2-A2`  | `1-A`    | 데이터 부가서비스 가입 페이지 | `page_view` / `data_addon_page`         | `comparison_action` | `data_addon`         | []                                     | nullable      | 페이지 진입만으로는 Event Feature를 만들지 않음        |
| Step2     | `2-A3`  | `1-A`    | 사용 상세 그래프 조회         | `page_view` / `usage_detail_chart`      | `inquiry_action`    | `usage_detail`       | []                                     | nullable      | 조회성 행동이므로 Behavioral Feature만 생성            |
| Step2     | `2-B1`  | `1-B`    | 청구 상세 항목 조회           | `page_view` / `billing_detail`          | `inquiry_action`    | `billing_detail`     | []                                     | nullable      | 조회성 행동이므로 Behavioral Feature만 생성            |
| Step2     | `2-B2`  | `1-B`    | 즉시 납부 버튼 클릭           | `click` / `pay_now_button`              | `decision_action`   | `payment`            | [`payment_retry`]                    | boolean       | 즉시 납부 버튼 클릭 시 생성                            |
| Step2     | `2-B3`  | `1-B`    | 자동납부 설정 변경            | `page_view` / `auto_pay_setting`        | `decision_action`   | `autopay`            | []                                     | nullable      | 설정 변경 행동은 Behavioral Feature로만 사용           |
| Step2     | `2-C1`  | `1-C`    | 요금제 변경 신청 클릭         | `click` / `plan_change_button`          | `decision_action`   | `plan_change`        | []                                     | nullable      | 신청 클릭 행동은 Behavioral Feature로만 사용           |
| Step2     | `2-C2`  | `1-C`    | 위약금 계산 페이지 진입       | `page_view` / `penalty_calc`            | `churn_action`      | `penalty`            | []                                     | nullable      | 위약금 조회는 이탈 Behavioral 신호로 처리              |
| Step2     | `2-C3`  | `1-C`    | 해지 신청 페이지 진입         | `page_view` / `cancel_page`             | `churn_action`      | `cancel`             | []                                     | nullable      | 해지 페이지 진입은 Behavioral Feature로만 사용         |
| Step2     | `2-D1`  | `1-D`    | 쿠폰 사용/혜택 적용 클릭      | `click` / `coupon_use`                  | `decision_action`   | `coupon`             | []                                     | nullable      | 혜택 적용 행동은 Behavioral 신호로 처리                |
| Step2     | `2-D2`  | `1-D`    | 멤버십 등급 혜택 조회         | `page_view` / `membership_tier`         | `inquiry_action`    | `membership_benefit` | []                                     | nullable      | 조회성 행동이므로 Behavioral Feature만 생성            |
| Step2     | `2-D3`  | `1-D`    | 이벤트/프로모션 페이지        | `page_view` / `promotion_event`         | `comparison_action` | `promotion_benefit`  | []                                     | nullable      | 혜택 탐색 Behavioral 신호로 처리                       |
| Step2     | `2-E1`  | `1-E`    | 요금제 탐색                   | `page_view` / `plan_explore`            | `comparison_action` | `plan_compare`       | []                                     | nullable      | 상품 탐색 Behavioral 신호로 처리                       |
| Step2     | `2-E2`  | `1-E`    | 단말기 탐색                   | `page_view` / `device_explore`          | `comparison_action` | `device`             | []                                     | nullable      | 단말 탐색 Behavioral 신호로 처리                       |
| Step2     | `2-E3`  | `1-E`    | 가족 결합 회선 추가 페이지    | `page_view` / `family_bundle`           | `comparison_action` | `family_bundle`      | []                                     | nullable      | 결합 탐색 Behavioral 신호로 처리                       |
| Step2     | `2-F1`  | `1-F`    | WiFi 진단 / 속도 측정 실행    | `click` / `quality_diagnosis`           | `diagnostic_action` | `quality_diagnosis`  | [`speed_test_run`]                   | boolean       | WiFi 진단 / 속도 측정 실행 시 생성                     |
| Step2     | `2-F2`  | `1-F`    | 챗봇 상담 진입                | `support_entry` / `chatbot`             | `support_action`    | `chatbot`            | [`support_entry`, `chatbot_start`] | boolean       | 챗봇 상담 진입 시 생성                                 |
| Step2     | `2-F3`  | `1-F`    | 전화 상담 연결 클릭           | `support_entry` / `call_support`        | `support_action`    | `support_consult`    | [`support_entry`, `call_cs_click`] | boolean       | 전화 상담 연결 클릭 시 생성                            |
| common    | `BACK`  | -          | 뒤로가기                      | `navigate_back` / `back_to_step1`       | `navigation_action` | `navigation`         | []                                     | nullable      | Step1 선택 화면으로 복귀하며, 관심사 이동 신호로 적재  |
| common    | `EXIT`  | -          | 앱 이탈                       | `app_exit` / `session_end`              | `exit_action`       | `session_exit`       | []                                     | nullable      | 세션 종료. Intent 재추론·Customer Context 갱신 없음   |

현재 문서는 Step1/Step2 선택지만으로 직접 생성되는 Event Feature만 사용한다. 그 외 신호는 본 문서의 Event Feature 범위에서 정의하지 않는다.

### 4.5. Behavioral Pattern Feature 정의

| Feature                             | 데이터 타입 | 생성 원천               | 계산 방법                                                                                                     | 의미                            |
| ----------------------------------- | ----------- | ----------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `explored_entity_count_5m`        | integer     | Step1/Step2 선택 Action | 최근 5분 내 distinct `behavior_entity` 수                                                                   | 관심 영역 다양성                |
| `action_intensity_5m`             | integer     | Step1/Step2 선택 Action | 최근 5분 내 전체 Step1/Step2 선택 Action 수                                                                   | 행동 활성도                     |
| `step1_menu_count_5m`             | integer     | Step1 선택 Action       | 최근 5분 내 `selected_step=step1` 횟수                                                                      | 상위 메뉴 진입 강도             |
| `step2_action_count_5m`           | integer     | Step2 선택 Action       | 최근 5분 내 `selected_step=step2` 횟수                                                                      | 구체 행동 실행 강도             |
| `menu_switch_count_5m`            | integer     | Step1/Step2 선택 Action | 최근 5분 내 서로 다른 Step1 상위 영역으로 전환된 횟수. Step2는 `parent_action_id` 기준으로 상위 영역을 판단 | 관심 영역 전환 강도             |
| `inquiry_action_count_5m`         | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_event_type=inquiry_action` 횟수                                                       | 정보 확인 강도                  |
| `comparison_action_count_5m`      | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_event_type=comparison_action` 횟수                                                    | 요금제/혜택/상품 비교 성향      |
| `decision_action_count_5m`        | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_event_type=decision_action` 횟수                                                      | 납부·변경·가입 실행 의향      |
| `diagnostic_action_count_5m`      | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_event_type=diagnostic_action` 횟수                                                    | 품질/장애 원인 확인 강도        |
| `support_action_count_5m`         | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_event_type=support_action` 횟수                                                       | 즉시 상담 필요 강도             |
| `churn_action_count_5m`           | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_event_type=churn_action` 횟수                                                         | 이탈 검토 강도                  |
| `navigation_back_count_5m`        | integer     | 공통 선택 Action        | 최근 5분 내 `selected_action_id=BACK` 횟수                                                                  | 탐색 되돌림/망설임              |
| `app_exit_count_5m`               | integer     | 공통 선택 Action        | 최근 5분 내 `selected_action_id=EXIT` 횟수                                                                  | 세션 종료 또는 이탈 행동        |
| `same_entity_repeat_count_5m`     | integer     | Step1/Step2 선택 Action | 최근 5분 내 동일 `behavior_entity` 최대 반복 횟수                                                           | 특정 문제/관심사 집중도         |
| `dominant_entity_5m`              | string enum | Step1/Step2 선택 Action | 최근 5분 내 가장 많이 발생한 `behavior_entity`, 없으면 `null`                                             | 현재 주요 관심 대상             |
| `last_entity`                     | string enum | Step1/Step2 선택 Action | 가장 최근 `behavior_entity`, 없으면 `null`                                                                | 현재 시점의 직접 관심 대상      |
| `entity_focus_ratio_5m`           | float       | Step1/Step2 선택 Action | `dominant_entity_5m` 발생 횟수 / `action_intensity_5m`; 분모가 0이면 0.0                                  | 특정 관심사 집중도              |
| `event_transition_pattern`        | string      | Step1/Step2 선택 Action | 최근 `behavior_event_type` 흐름을 `A -> B -> C` 형태로 저장                                               | 행동 변화                       |
| `entity_transition_pattern`       | string      | Step1/Step2 선택 Action | 최근 `behavior_entity` 흐름을 `A -> B -> C` 형태로 저장                                                   | 관심 영역 변화                  |
| `payment_retry_count_5m`          | integer     | 파생 Event Feature      | 최근 5분 내 `derived_event_features`에 `payment_retry`가 포함된 횟수                                      | 납부 실행/재시도 반복           |
| `autopay_setting_change_count_5m` | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_entity=autopay` AND `behavior_event_type=decision_action` 횟수                      | 자동납부 변경 시도              |
| `quality_diagnosis_count_5m`      | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_entity=quality_diagnosis` 횟수                                                        | 품질 진단 실행 강도             |
| `speed_test_count_5m`             | integer     | 파생 Event Feature      | 최근 5분 내 `derived_event_features`에 `speed_test_run`이 포함된 횟수                                     | 속도 문제 확인 강도             |
| `chatbot_start_count_5m`          | integer     | 파생 Event Feature      | 최근 5분 내 `derived_event_features`에 `chatbot_start`가 포함된 횟수                                      | 챗봇 상담 진입 강도             |
| `agent_connect_count_5m`          | integer     | Step1/Step2 선택 Action | 최근 5분 내 `behavior_entity=support_consult` 횟수                                                          | 사람 상담 연결 강도             |
| `support_after_diagnosis`         | boolean     | Step1/Step2 선택 Action | 최근 `quality_diagnosis` 이후 `support_action` 발생 여부                                                  | 진단 후 상담 전환               |
| `service_change_count_30d`        | integer     | Step1/Step2 선택 Action | 최근 30일 내 `plan_change`, `data_topup`, `autopay`, `family_bundle`, `cancel` 관련 구체 행동 횟수  | 상품/서비스 상태 변화 행동 빈도 |

### 4.6. Intent별 Behavioral Pattern Feature 예시

아래 예시는 Section 5의 핵심 Intent Metadata 중 대표 Intent에 대해, 해당 Intent의 Behavioral Pattern Feature 컬럼에 정의된 Feature만 사용해 행동 흐름과 값 예시를 보여준다.

| Intent ID | L3                 | 행동 흐름 예시                                                                                                                                        | 관련 Behavioral Pattern Feature                                                    | 예시 값                                                                                  | 해석                                                                     |
| --------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| INT-1110  | 데이터 사용량 조회 | Step1 데이터 사용량 페이지 진입 -> Step2 사용 상세 그래프 조회                                                                                        | `inquiry_action_count_5m`, `last_entity`                                       | `inquiry_action_count_5m=2`, `last_entity=usage_detail`                              | 최근 행동이 사용량 확인에 집중되어 데이터 사용량 조회 Intent가 상승      |
| INT-1210  | 월 요금 조회       | Step1 요금/청구 상세 페이지 진입 -> Step2 청구 상세 항목 조회 -> Step2 즉시 납부 버튼 클릭                                                            | `payment_retry_count_5m`, `inquiry_action_count_5m`                            | `payment_retry_count_5m=1`, `inquiry_action_count_5m=2`                              | 청구 확인 후 납부 행동이 이어져 월 요금 확인 Intent가 강화               |
| INT-3210  | 요금제 변경        | Step1 상품 탐색 페이지 진입 -> Step2 요금제 탐색 -> Step1 가입정보 페이지 진입 -> Step2 요금제 변경 신청 클릭                                         | `service_change_count_30d`, `decision_action_count_5m`                         | `service_change_count_30d=2`, `decision_action_count_5m=1`                           | 상품 비교 이후 실제 변경 신청 행동이 발생해 요금제 변경 가능성이 상승    |
| INT-4330  | 추천 요금제 검토   | Step1 상품 탐색 페이지 진입 -> Step2 요금제 탐색 -> Step2 단말기 탐색                                                                                 | `comparison_action_count_5m`, `service_change_count_30d`                       | `comparison_action_count_5m=3`, `service_change_count_30d=1`                         | 여러 대안을 비교하는 행동이 반복되어 추천 요금제 검토 Intent가 상승      |
| INT-5120  | WiFi 문제 해결     | Step1 고객지원 페이지 진입 -> Step2 WiFi 진단 / 속도 측정 실행 -> Step2 WiFi 진단 / 속도 측정 재실행                                                  | `quality_diagnosis_count_5m`, `speed_test_count_5m`                            | `quality_diagnosis_count_5m=2`, `speed_test_count_5m=2`                              | 동일 품질 진단 행동이 반복되어 WiFi 문제 해결 Intent가 직접 강화         |
| INT-5310  | 챗봇 상담          | Step1 고객지원 페이지 진입 -> Step2 챗봇 상담 진입                                                                                                    | `support_action_count_5m`, `chatbot_start_count_5m`                            | `support_action_count_5m=2`, `chatbot_start_count_5m=1`                              | 고객지원 흐름 안에서 챗봇을 실행해 셀프 상담 Intent가 상승               |
| INT-6110  | 가족결합 관리      | Step1 상품 탐색 페이지 진입 -> Step2 가족 결합 회선 추가 페이지 -> Step2 요금제 탐색                                                                  | `comparison_action_count_5m`, `service_change_count_30d`                       | `comparison_action_count_5m=2`, `service_change_count_30d=1`                         | 가족결합 관련 탐색과 상품 비교가 결합되어 가족결합 관리 Intent가 상승    |
| INT-7130  | 해지 상담 요청     | Step1 가입정보 페이지 진입 -> Step2 위약금 계산 페이지 진입 -> Step2 해지 신청 페이지 진입 -> Step1 고객지원 페이지 진입 -> Step2 전화 상담 연결 클릭 | `support_action_count_5m`, `agent_connect_count_5m`, `churn_action_count_5m` | `support_action_count_5m=2`, `agent_connect_count_5m=1`, `churn_action_count_5m=2` | 해지 검토 행동 이후 사람 상담 연결이 발생해 해지 상담 요청 Intent가 상승 |

### 4.7. 예시 Output: Behavior Pattern Feature Table

| 출력 컬럼                                        | 데이터 타입        | 설명                                         |
| ------------------------------------------------ | ------------------ | -------------------------------------------- |
| `window_end`                                   | datetime/string    | 집계 윈도우 종료 시각                        |
| `session_id`                                   | string             | 세션 ID                                      |
| `cust_id`                                      | string             | 고객 ID                                      |
| `selected_step`                                | string enum        | 가장 최근 선택 단계                          |
| `selected_action_id`                           | string             | 가장 최근 행동 ID                            |
| `parent_action_id`                             | string/null        | Step2의 상위 Step1 ID                        |
| `behavior_event_type`                          | string enum        | 가장 최근 정규화 행동 유형                   |
| `behavior_entity`                              | string enum        | 가장 최근 정규화 관심 대상                   |
| `derived_event_features`                       | array `<string>` | 가장 최근 선택에서 파생된 Event Feature 목록 |
| `*_count_5m`, `*_count_30d`, `*_count_24h` | integer            | 윈도우 내 조건별 발생 횟수                   |
| `*_after_*`                                    | boolean            | 특정 순서 패턴 발생 여부                     |
| `dominant_entity_5m`                           | string enum/null   | 최근 5분 내 최빈 entity                      |
| `event_transition_pattern`                     | string             | 최근 behavior_event_type 시퀀스              |
| `entity_transition_pattern`                    | string             | 최근 behavior_entity 시퀀스                  |
| `last_entity`                                  | string enum/null   | 가장 최근 entity                             |
| `entity_focus_ratio_5m`                        | float              | 최빈 entity 비중                             |

| window_end | session_id | cust_id | selected_step | selected_action_id | parent_action_id | behavior_event_type | behavior_entity     | derived_event_features                 | action_intensity_5m | step1_menu_count_5m | step2_action_count_5m | inquiry_action_count_5m | comparison_action_count_5m | decision_action_count_5m | diagnostic_action_count_5m | support_action_count_5m | churn_action_count_5m | payment_retry_count_5m | speed_test_count_5m | chatbot_start_count_5m | agent_connect_count_5m | support_after_diagnosis | dominant_entity_5m    | event_transition_pattern                                                                                       | entity_transition_pattern                                                                  | last_entity         | entity_focus_ratio_5m |
| ---------- | ---------- | ------- | ------------- | ------------------ | ---------------- | ------------------- | ------------------- | -------------------------------------- | ------------------- | ------------------- | --------------------- | ----------------------- | -------------------------- | ------------------------ | -------------------------- | ----------------------- | --------------------- | ---------------------- | ------------------- | ---------------------- | ---------------------- | ----------------------- | --------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------- | --------------------- |
| 12:05      | S001       | A001    | `step2`     | `2-F3`           | `1-F`          | `support_action`  | `support_consult` | [`support_entry`, `call_cs_click`] | 6                   | 2                   | 4                     | 2                       | 0                          | 2                        | 0                          | 2                       | 0                     | 2                      | 0                   | 0                      | 1                      | false                   | `payment`           | `inquiry_action -> inquiry_action -> decision_action -> decision_action -> support_action -> support_action` | `billing -> billing_detail -> payment -> payment -> customer_support -> support_consult` | `support_consult` | 0.33                  |
| 12:05      | S002       | A002    | `step2`     | `2-F2`           | `1-F`          | `support_action`  | `chatbot`         | [`support_entry`, `chatbot_start`] | 4                   | 1                   | 3                     | 0                       | 0                          | 0                        | 2                          | 2                       | 0                     | 0                      | 2                   | 1                      | 0                      | true                    | `quality_diagnosis` | `support_action -> diagnostic_action -> diagnostic_action -> support_action`                                 | `customer_support -> quality_diagnosis -> quality_diagnosis -> chatbot`                  | `chatbot`         | 0.50                  |
| 12:05      | S003       | A003    | `step2`     | `2-C3`           | `1-C`          | `churn_action`    | `cancel`          | []                                     | 4                   | 1                   | 3                     | 1                       | 0                          | 0                        | 0                          | 0                       | 3                     | 0                      | 0                   | 0                      | 0                      | false                   | `penalty`           | `inquiry_action -> churn_action -> churn_action -> churn_action`                                             | `subscription_info -> penalty -> penalty -> cancel`                                      | `cancel`          | 0.50                  |
| 12:05      | S004       | A004    | `step2`     | `2-D1`           | `1-D`          | `decision_action` | `coupon`          | []                                     | 4                   | 1                   | 3                     | 2                       | 1                          | 1                        | 0                          | 0                       | 0                     | 0                      | 0                   | 0                      | 0                      | false                   | `coupon`            | `inquiry_action -> inquiry_action -> comparison_action -> decision_action`                                   | `benefit_membership -> membership_benefit -> promotion_benefit -> coupon`                | `coupon`          | 0.25                  |

---

## 5. 핵심 Intent Metadata

아래 표는 시연 핵심 Intent에 대한 상세 정의다. 비시연 Intent는 Section 1.3의 L1/L2 원칙을 따른다. `방법론 상세`은 아래 기준으로 작성한다.

* `Rule`: 직접 Trigger 조건, Batch 보정, Behavioral 보정, 최종 score 결정 방식을 명시한다.
* `Model`: 예측 대상, 주요 입력 Feature, 상호작용 Feature, 최종 score 산출 방식을 명시한다.
* `Rule baseline`: 현재 Step1/Step2에서 실시간 신호가 없는 경우, Batch baseline 유지 사유와 score 변경 범위를 명시한다.

| L1             | L2               | L3                 | Intent ID | Batch Feature                                                                                                                                                                      | Event Feature                                                                                                          | Behavioral Pattern Feature                                                                                                                               | 방법론 | 방법론 상세                                                                                                                                                                                                                                                                                                                                                                                                                                                              | 시연상 의미                                       |
| -------------- | ---------------- | ------------------ | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------- |
| My 정보 조회   | 사용량 조회      | 데이터 사용량 조회 | INT-1110  | `data_usage_rate` (데이터 사용률), `remaining_data_ratio` (잔여 데이터 비율), `usage_intensity_index` (사용 강도 Index)                                                      | -                                                                                                                      | `inquiry_action_count_5m` (정보 확인 강도), `last_entity` (현재 시점의 직접 관심 대상)                                                               | Rule   | Rule: Trigger=`last_entity=usage_detail` 또는 `inquiry_action_count_5m>=2`; Batch=`data_usage_rate>=0.7` 또는 `remaining_data_ratio<=0.3`이면 baseline 상향; 최종 score는 Batch score와 Trigger score 중 큰 값을 쓰고 `usage_intensity_index`로 보정.                                                                                                                                                                                                          | 설문상 데이터 부족 고객이 데이터 확인 의도를 보임 |
| My 정보 조회   | 사용량 조회      | 로밍 사용량 조회   | INT-1140  | `roaming_history_count_1y` (로밍 이력), `overseas_trip_count_1y` (해외 출국 빈도), `roaming_intent_score` (로밍 의향 Score)                                                  | -                                                                                                                      | -                                                                                                                                                        | Rule   | Rule baseline: 현재 Step1/Step2에 로밍 entity가 없어 Event/Behavior boost는 적용하지 않음;`roaming_intent_score`를 최종 score의 주 입력으로 유지; 해외/로밍 이력이 없으면 낮은 baseline으로 고정.                                                                                                                                                                                                                                                                      | 출국/해외 이용 이력 기반 관심도                   |
| My 정보 조회   | 청구 조회        | 월 요금 조회       | INT-1210  | `monthly_fee` (요금제 월정액), `cost_burden_score` (비용 부담도), `bill_shock_count_6m` (청구 급증 경험 6m)                                                                  | `payment_retry` (납부 실행/재시도 의도)                                                                              | `payment_retry_count_5m` (납부 실행/재시도 반복), `inquiry_action_count_5m` (정보 확인 강도)                                                         | Rule   | Rule: Trigger=`payment_retry=True` 또는 `payment_retry_count_5m>=1`; Batch=`cost_burden_score`와 `bill_shock_count_6m`로 요금 확인 baseline 산출; `inquiry_action_count_5m>=1`이면 납부 전후 조회 evidence로 score 보정.                                                                                                                                                                                                                                       | 납부 전후 요금 확인 의도가 커짐                   |
| My 정보 조회   | 청구 조회        | 청구 상세 조회     | INT-1220  | `bill_shock_count_6m` (청구 급증 경험 6m), `price_sensitivity_index` (요금 민감도 Index), `cost_burden_score` (비용 부담도)                                                  | `payment_retry` (납부 실행/재시도 의도)                                                                              | `inquiry_action_count_5m` (정보 확인 강도), `payment_retry_count_5m` (납부 실행/재시도 반복)                                                         | Rule   | Rule: Trigger=`inquiry_action_count_5m>=2` 또는 `payment_retry_count_5m>=1`; Batch=`bill_shock_count_6m`, `price_sensitivity_index`, `cost_burden_score`로 상세 확인 필요도 산출; 납부 재시도는 청구 상세 확인 boost로만 반영.                                                                                                                                                                                                                                 | 요금이 왜 올랐는지 확인하려는 의도                |
| My 정보 조회   | 청구 조회        | 미납 요금 조회     | INT-1240  | `cost_burden_score` (비용 부담도), `bill_shock_count_6m` (청구 급증 경험 6m), `price_sensitivity_index` (요금 민감도 Index)                                                  | `payment_retry` (납부 실행/재시도 의도)                                                                              | `payment_retry_count_5m` (납부 실행/재시도 반복), `decision_action_count_5m` (납부·변경·가입 실행 의향)                                            | Rule   | Rule: Trigger=`payment_retry=True` 또는 `payment_retry_count_5m>=1`; Batch=`cost_burden_score`와 `price_sensitivity_index`로 미납 확인 가능성 산출; `decision_action_count_5m`는 납부 실행 직전 상태 확인 boost로 반영.                                                                                                                                                                                                                                        | 납부 전 상태 확인                                 |
| My 정보 조회   | 가입정보 조회    | 약정 조회          | INT-1330  | `tenure_months` (가입 개월 수), `contract_progress_rate` (약정 진행률), `churn_risk_score` (이탈 위험 Score)                                                                 | -                                                                                                                      | `churn_action_count_5m` (이탈 검토 강도), `dominant_entity_5m` (현재 주요 관심 대상)                                                                 | Rule   | Rule: Trigger=`churn_action_count_5m>=1`; Batch=`contract_progress_rate`와 `tenure_months`로 약정 조회 baseline 산출; `dominant_entity_5m in (subscription_info, penalty)`이면 `churn_risk_score`를 해지 전 조회 맥락 보정값으로 반영.                                                                                                                                                                                                                         | 변경/해지 전 약정 조건 확인                       |
| My 정보 조회   | 가입정보 조회    | 결합상품 조회      | INT-1340  | `bundle_yn` (결합 여부), `bundle_type` (결합 형태), `family_line_count` (가족 회선 수), `bundle_expansion_score` (결합 확장 Score)                                         | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `service_change_count_30d` (상품/서비스 상태 변화 행동 빈도)                              | Rule   | Rule: Trigger=`comparison_action_count_5m>=1` 또는 `service_change_count_30d>=1`; Batch=`bundle_yn`, `bundle_type`, `family_line_count`로 결합 조회 baseline 산출; `bundle_expansion_score`가 높으면 결합 할인/구성 확인 score를 상향.                                                                                                                                                                                                                       | 결합 구성과 할인 상태 확인                        |
| My 정보 조회   | 혜택 조회        | 멤버십 조회        | INT-1410  | `membership_engagement_score` (멤버십 활용도), `customer_value_index` (고객 가치 Index), `exploration_propensity_index` (탐색 성향 Index)                                    | -                                                                                                                      | `inquiry_action_count_5m` (정보 확인 강도), `dominant_entity_5m` (현재 주요 관심 대상)                                                               | Rule   | Rule: Trigger=`inquiry_action_count_5m>=1`이고 `dominant_entity_5m in (benefit_membership, membership_benefit)`이면 적용; Batch=`membership_engagement_score`를 주 baseline으로 사용; `customer_value_index`와 `exploration_propensity_index`로 VIP/혜택 수용도 보정.                                                                                                                                                                                          | 혜택 확인/활용 의도                               |
| My 정보 조회   | 혜택 조회        | 쿠폰 조회          | INT-1430  | `membership_engagement_score` (멤버십 활용도), `exploration_propensity_index` (탐색 성향 Index), `cost_burden_score` (비용 부담도)                                           | -                                                                                                                      | `decision_action_count_5m` (납부·변경·가입 실행 의향), `last_entity` (현재 시점의 직접 관심 대상)                                                  | Rule   | Rule: Trigger=`last_entity=coupon` 또는 `decision_action_count_5m>=1`; Batch=`membership_engagement_score`와 `exploration_propensity_index`로 쿠폰 조회 baseline 산출; `cost_burden_score`가 높으면 비용 절감 목적 boost 적용.                                                                                                                                                                                                                                 | 즉시 할인/쿠폰 사용 관심                          |
| 상품 탐색/가입 | 모바일 상품 탐색 | 요금제 탐색        | INT-2110  | `price_sensitivity_index` (요금 민감도 Index), `data_usage_rate` (데이터 사용률), `contract_progress_rate` (약정 진행률), `churn_risk_score` (이탈 위험 Score)             | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `dominant_entity_5m` (현재 주요 관심 대상)                                                | Rule   | Rule: Trigger=`comparison_action_count_5m>=1`이고 `dominant_entity_5m in (product_explore, plan_compare, plan_change)`이면 적용; Batch=`price_sensitivity_index`, `data_usage_rate`, `contract_progress_rate`로 탐색 baseline 산출; `churn_risk_score`는 대안 탐색 boost로 반영.                                                                                                                                                                             | 더 적합한 요금제 탐색                             |
| 상품 탐색/가입 | 모바일 상품 탐색 | 5G 상품 탐색       | INT-2120  | `upsell_fit_score` (업셀 적합도 Score), `data_usage_rate` (데이터 사용률), `usage_intensity_index` (사용 강도 Index), `plan_tier` (요금제 구간)                            | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `dominant_entity_5m` (현재 주요 관심 대상)                                                | Rule   | Rule: Trigger=`comparison_action_count_5m>=1`이고 `dominant_entity_5m in (product_explore, plan_compare)`이면 적용; Batch=`upsell_fit_score`, `data_usage_rate`, `usage_intensity_index`로 5G 탐색 baseline 산출; `plan_tier`가 premium이 아니면 상위 상품 전환 여지로 보정.                                                                                                                                                                                 | 상위 요금제/5G 전환 검토                          |
| 상품 탐색/가입 | 모바일 상품 탐색 | 실속형 상품 탐색   | INT-2150  | `price_sensitivity_index` (요금 민감도 Index), `cost_burden_score` (비용 부담도), `monthly_fee` (요금제 월정액)                                                              | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `service_change_count_30d` (상품/서비스 상태 변화 행동 빈도)                              | Rule   | Rule: Trigger=`comparison_action_count_5m>=1` 또는 `service_change_count_30d>=1`; Batch=`price_sensitivity_index`와 `cost_burden_score`로 절감 탐색 baseline 산출; `monthly_fee`가 높으면 실속형 대안 탐색 score 상향.                                                                                                                                                                                                                                         | 통신비 절감 목적의 상품 탐색                      |
| 상품 탐색/가입 | 모바일 상품 탐색 | 데이터 상품 탐색   | INT-2130  | `data_usage_rate` (데이터 사용률), `remaining_data_ratio` (잔여 데이터 비율), `usage_intensity_index` (사용 강도 Index), `upsell_fit_score` (업셀 적합도 Score)            | -                                                                                                                      | `decision_action_count_5m` (납부·변경·가입 실행 의향), `comparison_action_count_5m` (요금제/혜택/상품 비교 성향)                                   | Model  | Model: 예측 대상=데이터 충전/부가상품 탐색 가능성; 입력=`data_usage_rate`, `remaining_data_ratio`, `usage_intensity_index`, `upsell_fit_score`, `comparison_action_count_5m`, `decision_action_count_5m`; 상호작용=`remaining_data_ratio` 낮음 x `decision_action_count_5m`; 최종 score=모델 확률값.                                                                                                                                                     | 데이터 충전 vs 요금제 변경 판단                   |
| 상품 탐색/가입 | 모바일 상품 탐색 | 로밍 상품 탐색     | INT-2140  | `roaming_history_count_1y` (로밍 이력), `overseas_trip_count_1y` (해외 출국 빈도), `roaming_intent_score` (로밍 의향 Score)                                                  | -                                                                                                                      | -                                                                                                                                                        | Rule   | Rule baseline: 현재 Step1/Step2에 로밍 탐색 행동이 없어 실시간 boost는 미적용;`roaming_intent_score`와 해외 방문 이력으로 baseline score만 산출; 행동 발생 전에는 rank 변화가 제한됨.                                                                                                                                                                                                                                                                                  | 출국 전 로밍 상품 검토                            |
| 상품 탐색/가입 | 가입/구매 실행   | 로밍 가입          | INT-2540  | `roaming_intent_score` (로밍 의향 Score), `roaming_history_count_1y` (로밍 이력), `overseas_trip_count_1y` (해외 출국 빈도)                                                  | -                                                                                                                      | -                                                                                                                                                        | Rule   | Rule baseline: 현재 Step1/Step2에 로밍 가입 Trigger가 없어 가입 실행 score는 `roaming_intent_score` 기반 baseline으로만 유지; `roaming_history_count_1y`와 `overseas_trip_count_1y`가 모두 낮으면 낮은 가입 가능성으로 고정.                                                                                                                                                                                                                                       | 실제 로밍 가입/설정 가능성                        |
| 상품 탐색/가입 | 단말 탐색        | 스마트폰 탐색      | INT-2410  | `device_age_months` (단말 사용 기간), `device_replacement_intent_score` (단말 교체 의향 Score), `contract_progress_rate` (약정 진행률)                                       | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `dominant_entity_5m` (현재 주요 관심 대상)                                                | Rule   | Rule: Trigger=`comparison_action_count_5m>=1`이고 `dominant_entity_5m=device`이면 적용; Batch=`device_replacement_intent_score`, `device_age_months`, `contract_progress_rate`로 baseline 산출; 단말 사용 기간이 길수록 boost.                                                                                                                                                                                                                                 | 단말 교체 관심                                    |
| 상품 탐색/가입 | 단말 탐색        | 중고폰 보상 탐색   | INT-2440  | `device_replacement_intent_score` (단말 교체 의향 Score), `price_sensitivity_index` (요금 민감도 Index), `device_age_months` (단말 사용 기간)                                | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `dominant_entity_5m` (현재 주요 관심 대상)                                                | Rule   | Rule: Trigger=`comparison_action_count_5m>=1`이고 `dominant_entity_5m=device`이면 적용; Batch=`device_replacement_intent_score`와 `device_age_months`로 교체 필요도 산출; `price_sensitivity_index`가 높으면 보상/절감 수단 탐색 score 상향.                                                                                                                                                                                                                   | 교체 비용 절감 수단 탐색                          |
| 상품 탐색/가입 | 가입/구매 실행   | 단말 구매          | INT-2530  | `device_replacement_intent_score` (단말 교체 의향 Score), `customer_value_index` (고객 가치 Index), `contract_progress_rate` (약정 진행률)                                   | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `decision_action_count_5m` (납부·변경·가입 실행 의향)                                   | Rule   | Rule: Trigger=`comparison_action_count_5m>=1` 이후 `decision_action_count_5m>=1`; Batch=`device_replacement_intent_score`, `contract_progress_rate`, `customer_value_index`로 구매 baseline 산출; 탐색 후 실행 행동이 붙을 때 구매 score를 직접 상향.                                                                                                                                                                                                          | 탐색에서 구매 실행으로 전환                       |
| 셀프처리       | 요금/납부 처리   | 즉시 납부          | INT-3110  | `cost_burden_score` (비용 부담도), `price_sensitivity_index` (요금 민감도 Index), `bill_shock_count_6m` (청구 급증 경험 6m)                                                  | `payment_retry` (납부 실행/재시도 의도)                                                                              | `payment_retry_count_5m` (납부 실행/재시도 반복), `decision_action_count_5m` (납부·변경·가입 실행 의향)                                            | Rule   | Rule: Trigger=`payment_retry=True`; Batch=`cost_burden_score`, `price_sensitivity_index`, `bill_shock_count_6m`는 납부 필요도 baseline; `payment_retry_count_5m`가 반복되면 즉시 납부 score를 최상위 후보로 고정하고 `decision_action_count_5m`로 실행 강도 보정.                                                                                                                                                                                            | 납부 실행 의도                                    |
| 셀프처리       | 요금/납부 처리   | 자동이체 변경      | INT-3120  | `cost_burden_score` (비용 부담도), `tenure_months` (가입 개월 수)                                                                                                              | -                                                                                                                      | `autopay_setting_change_count_5m` (자동납부 변경 시도), `decision_action_count_5m` (납부·변경·가입 실행 의향)                                      | Rule   | Rule: Trigger=`autopay_setting_change_count_5m>=1`; Batch=`cost_burden_score`와 `tenure_months`로 납부 방식 변경 baseline 산출; `decision_action_count_5m`는 실제 설정 변경 실행 강도 보정.                                                                                                                                                                                                                                                                      | 납부 방식 변경                                    |
| 셀프처리       | 회선/서비스 처리 | 요금제 변경        | INT-3210  | `price_sensitivity_index` (요금 민감도 Index), `data_usage_rate` (데이터 사용률), `churn_risk_score` (이탈 위험 Score), `contract_progress_rate` (약정 진행률)             | -                                                                                                                      | `service_change_count_30d` (상품/서비스 상태 변화 행동 빈도), `decision_action_count_5m` (납부·변경·가입 실행 의향)                                | Model  | Model: 예측 대상=요금제 변경 실행 가능성; 입력=`price_sensitivity_index`, `data_usage_rate`, `churn_risk_score`, `contract_progress_rate`, `service_change_count_30d`, `decision_action_count_5m`; 최종 score=0.25*`price_sensitivity_index`/100 + 0.25*`data_usage_rate` + 0.20*`churn_risk_score` + 0.15*`contract_progress_rate` + 0.10*min(`service_change_count_30d`/3, 1) + 0.05*min(`decision_action_count_5m`/3, 1).                     | 실제 요금제 변경 가능성                           |
| 혜택/프로모션  | 할인 혜택 탐색   | 쿠폰 탐색          | INT-4110  | `price_sensitivity_index` (요금 민감도 Index), `cost_burden_score` (비용 부담도), `membership_engagement_score` (멤버십 활용도)                                              | -                                                                                                                      | `decision_action_count_5m` (납부·변경·가입 실행 의향), `dominant_entity_5m` (현재 주요 관심 대상)                                                  | Rule   | Rule: Trigger=`decision_action_count_5m>=1`이고 `dominant_entity_5m in (coupon, membership_benefit, promotion_benefit)`이면 적용; Batch=`price_sensitivity_index`, `cost_burden_score`, `membership_engagement_score`로 쿠폰 탐색 baseline 산출; 비용 부담이 높을수록 할인 목적 boost.                                                                                                                                                                         | 혜택으로 비용을 줄이려는 의도                     |
| 혜택/프로모션  | 맞춤 추천 탐색   | AI 추천 탐색       | INT-4310  | `recommendation_fit_score` (추천 적합도 Score), `customer_value_index` (고객 가치 Index), `usage_intensity_index` (사용 강도 Index), `ott_usage_frequency` (OTT 사용 빈도) | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `dominant_entity_5m` (현재 주요 관심 대상)                                                | Model  | Model: 예측 대상=AI 추천 수용 가능성; 입력=`recommendation_fit_score`, `customer_value_index`, `usage_intensity_index`, `ott_usage_frequency`, `comparison_action_count_5m`, `dominant_entity_5m`; 상호작용=`recommendation_fit_score` 높음 x `dominant_entity_5m in (product_explore, benefit_membership, promotion_benefit)`; 최종 score=모델 확률값.                                                                                                  | 개인화 추천 수용 가능성                           |
| 혜택/프로모션  | 맞춤 추천 탐색   | 개인화 혜택 탐색   | INT-4320  | `customer_value_index` (고객 가치 Index), `membership_engagement_score` (멤버십 활용도), `exploration_propensity_index` (탐색 성향 Index)                                    | -                                                                                                                      | `inquiry_action_count_5m` (정보 확인 강도), `comparison_action_count_5m` (요금제/혜택/상품 비교 성향)                                                | Model  | Model: 예측 대상=개인화 혜택 탐색 가능성; 입력=`customer_value_index`, `membership_engagement_score`, `exploration_propensity_index`, `inquiry_action_count_5m`, `comparison_action_count_5m`; 상호작용=멤버십 활용도 높음 x 혜택 조회/비교 반복; 최종 score=모델 확률값.                                                                                                                                                                                      | 고객별 혜택 추천                                  |
| 혜택/프로모션  | 맞춤 추천 탐색   | 추천 요금제 검토   | INT-4330  | `price_sensitivity_index` (요금 민감도 Index), `data_usage_rate` (데이터 사용률), `contract_progress_rate` (약정 진행률), `recommendation_fit_score` (추천 적합도 Score)   | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `service_change_count_30d` (상품/서비스 상태 변화 행동 빈도)                              | Model  | Model: 예측 대상=추천 요금제 검토 가능성; 입력=`recommendation_fit_score`, `data_usage_rate`, `price_sensitivity_index`, `contract_progress_rate`, `comparison_action_count_5m`, `service_change_count_30d`; 최종 score=0.30*`recommendation_fit_score` + 0.25*`data_usage_rate` + 0.20*`price_sensitivity_index`/100 + 0.15*`contract_progress_rate` + 0.05*min(`comparison_action_count_5m`/3, 1) + 0.05*min(`service_change_count_30d`/3, 1). | 현재 요금제보다 나은 대안 검토                    |
| 문제 해결/상담 | 인증/로그인 문제 | 로그인 오류 해결   | INT-5210  | `age` (나이), `support_contact_count_30d` (30일 상담 횟수), `quality_complaint_score` (품질 불만 Score)                                                                      | `support_entry` (고객지원 진입), `call_cs_click` (상담사 연결 의도)                                                | `support_action_count_5m` (즉시 상담 필요 강도), `agent_connect_count_5m` (사람 상담 연결 강도)                                                      | Rule   | Rule: 현재 직접 인증 Event가 없으므로 `support_entry=True` 또는 `call_cs_click=True`을 보조 Trigger로 사용; Batch=`support_contact_count_30d`, `age`, `quality_complaint_score`로 상담 필요도 baseline 산출; `agent_connect_count_5m`가 있으면 로그인 문제 상담 후보로 보정.                                                                                                                                                                                 | 앱 이용 진입 문제 상담 가능성                     |
| 문제 해결/상담 | 결제 오류 해결   | 결제 오류 해결     | INT-5220  | `cost_burden_score` (비용 부담도), `price_sensitivity_index` (요금 민감도 Index), `support_contact_count_30d` (30일 상담 횟수)                                               | `payment_retry` (납부 실행/재시도 의도), `support_entry` (고객지원 진입), `call_cs_click` (상담사 연결 의도)     | `payment_retry_count_5m` (납부 실행/재시도 반복), `support_action_count_5m` (즉시 상담 필요 강도), `agent_connect_count_5m` (사람 상담 연결 강도)  | Rule   | Rule: Trigger=`payment_retry_count_5m>=2` 또는 `payment_retry=True` 이후 `support_entry=True`; Batch=`cost_burden_score`, `price_sensitivity_index`, `support_contact_count_30d`로 결제 지원 baseline 산출; `agent_connect_count_5m`가 있으면 오류 해결 score를 강하게 상향.                                                                                                                                                                               | 납부 과정 지원 필요                               |
| 문제 해결/상담 | 품질 문제 해결   | 인터넷 장애 해결   | INT-5110  | `quality_satisfaction_score` (품질 만족도), `quality_complaint_score` (품질 불만 Score), `bundle_yn` (결합 여부), `bundle_type` (결합 형태)                                | `speed_test_run` (품질/속도 문제 확인 의도), `support_entry` (고객지원 진입), `call_cs_click` (상담사 연결 의도) | `quality_diagnosis_count_5m` (품질 진단 실행 강도), `support_after_diagnosis` (진단 후 상담 전환), `support_action_count_5m` (즉시 상담 필요 강도) | Model  | Model: 예측 대상=인터넷/홈상품 장애 가능성; 입력=`quality_satisfaction_score`, `quality_complaint_score`, `bundle_yn`, `bundle_type`, `speed_test_run`, `quality_diagnosis_count_5m`, `support_after_diagnosis`; 상호작용=홈 결합 x 진단 반복 x 상담 전환; 최종 score=모델 확률값.                                                                                                                                                                         | 인터넷/홈상품 품질 문제 가능성                    |
| 문제 해결/상담 | 품질 문제 해결   | WiFi 문제 해결     | INT-5120  | `quality_satisfaction_score` (품질 만족도), `quality_complaint_score` (품질 불만 Score), `bundle_type` (결합 형태)                                                           | `speed_test_run` (품질/속도 문제 확인 의도)                                                                          | `quality_diagnosis_count_5m` (품질 진단 실행 강도), `speed_test_count_5m` (속도 문제 확인 강도)                                                      | Model  | Model: 예측 대상=WiFi 문제 해결 가능성; 입력=`quality_satisfaction_score`, `quality_complaint_score`, `bundle_type`, `speed_test_run`, `quality_diagnosis_count_5m`, `speed_test_count_5m`; 상호작용=속도측정 실행 x 진단 반복; 최종 score=모델 확률값.                                                                                                                                                                                                      | WiFi 진단/개선 필요                               |
| 문제 해결/상담 | 품질 문제 해결   | 속도 저하 해결     | INT-5130  | `quality_satisfaction_score` (품질 만족도), `data_usage_rate` (데이터 사용률), `usage_intensity_index` (사용 강도 Index)                                                     | `speed_test_run` (품질/속도 문제 확인 의도)                                                                          | `speed_test_count_5m` (속도 문제 확인 강도), `quality_diagnosis_count_5m` (품질 진단 실행 강도)                                                      | Model  | Model: 예측 대상=체감 속도 저하 해결 가능성; 입력=`quality_satisfaction_score`, `data_usage_rate`, `usage_intensity_index`, `speed_test_run`, `speed_test_count_5m`, `quality_diagnosis_count_5m`; 상호작용=사용 강도 높음 x 속도측정 반복; 최종 score=모델 확률값.                                                                                                                                                                                          | 체감 속도 저하 해결                               |
| 문제 해결/상담 | 품질 문제 해결   | IPTV 장애 해결     | INT-5140  | `bundle_type` (결합 형태), `quality_satisfaction_score` (품질 만족도), `quality_complaint_score` (품질 불만 Score)                                                           | `speed_test_run` (품질/속도 문제 확인 의도)                                                                          | `quality_diagnosis_count_5m` (품질 진단 실행 강도), `support_after_diagnosis` (진단 후 상담 전환)                                                    | Rule   | Rule: Trigger=`speed_test_run=True` 이후 `support_after_diagnosis=true`; Batch=`bundle_type`이 home/full이면 IPTV 장애 baseline 부여; `quality_complaint_score`와 `quality_satisfaction_score`로 기술 지원 필요도 보정.                                                                                                                                                                                                                                        | IPTV 품질 상담 가능성                             |
| 문제 해결/상담 | 품질 문제 해결   | QoE 문제 해결      | INT-5150  | `quality_satisfaction_score` (품질 만족도), `usage_intensity_index` (사용 강도 Index), `ott_usage_frequency` (OTT 사용 빈도)                                                 | `speed_test_run` (품질/속도 문제 확인 의도)                                                                          | `speed_test_count_5m` (속도 문제 확인 강도), `quality_diagnosis_count_5m` (품질 진단 실행 강도)                                                      | Rule   | Rule: Trigger=`speed_test_run=True` 또는 `speed_test_count_5m>=1`; Batch=`usage_intensity_index`와 `ott_usage_frequency`로 QoE 민감도 baseline 산출; `quality_diagnosis_count_5m` 반복 시 체감 품질 문제 score 상향.                                                                                                                                                                                                                                           | 서비스 체감 품질 개선                             |
| 문제 해결/상담 | 고객 상담        | 챗봇 상담          | INT-5310  | `support_contact_count_30d` (30일 상담 횟수), `age` (나이)                                                                                                                     | `chatbot_start` (챗봇 기반 셀프 상담 진입), `support_entry` (고객지원 진입)                                        | `support_action_count_5m` (즉시 상담 필요 강도), `chatbot_start_count_5m` (챗봇 상담 진입 강도)                                                      | Rule   | Rule: Trigger=`chatbot_start=True` 또는 `chatbot_start_count_5m>=1`; Batch=`support_contact_count_30d`와 `age`로 상담 채널 baseline 산출; `support_action_count_5m`는 고객지원 흐름 내 챗봇 실행 강도 보정.                                                                                                                                                                                                                                                    | 셀프 상담 진입                                    |
| 문제 해결/상담 | 고객 상담        | 채팅 상담          | INT-5320  | `support_contact_count_30d` (30일 상담 횟수), `quality_complaint_score` (품질 불만 Score)                                                                                      | `support_entry` (고객지원 진입), `chatbot_start` (챗봇 기반 셀프 상담 진입)                                        | `support_action_count_5m` (즉시 상담 필요 강도), `chatbot_start_count_5m` (챗봇 상담 진입 강도)                                                      | Rule   | Rule: Trigger=`support_entry=True` 이후 `chatbot_start=True`; Batch=`support_contact_count_30d`와 `quality_complaint_score`로 채팅 상담 필요도 baseline 산출; `support_action_count_5m`가 반복되면 상담 채널 전환 가능성으로 score 보정.                                                                                                                                                                                                                       | 채팅 기반 상담 필요                               |
| 문제 해결/상담 | 고객 상담        | 전화 상담          | INT-5330  | `support_contact_count_30d` (30일 상담 횟수), `age` (나이), `quality_complaint_score` (품질 불만 Score)                                                                      | `call_cs_click` (상담사 연결 의도), `support_entry` (고객지원 진입)                                                | `support_action_count_5m` (즉시 상담 필요 강도), `agent_connect_count_5m` (사람 상담 연결 강도)                                                      | Rule   | Rule: Trigger=`call_cs_click=True` 또는 `agent_connect_count_5m>=1`; Batch=`support_contact_count_30d`, `age`, `quality_complaint_score`로 사람 상담 baseline 산출; `support_action_count_5m`가 높으면 즉시 해결 필요도를 보정.                                                                                                                                                                                                                              | 빠른 해결 또는 고난도 상담                        |
| 문제 해결/상담 | AS/지원 요청     | AS 신청            | INT-5410  | `quality_complaint_score` (품질 불만 Score), `quality_satisfaction_score` (품질 만족도), `bundle_type` (결합 형태)                                                           | `speed_test_run` (품질/속도 문제 확인 의도), `support_entry` (고객지원 진입), `call_cs_click` (상담사 연결 의도) | `quality_diagnosis_count_5m` (품질 진단 실행 강도), `support_after_diagnosis` (진단 후 상담 전환), `support_action_count_5m` (즉시 상담 필요 강도) | Rule   | Rule: Trigger=`support_after_diagnosis=true` 또는 `call_cs_click=True`; Batch=`quality_complaint_score`, `quality_satisfaction_score`, `bundle_type`으로 AS 필요도 baseline 산출; `quality_diagnosis_count_5m`와 `support_action_count_5m`가 함께 높으면 기술 지원 score 상향.                                                                                                                                                                             | 현장/기술 지원 필요                               |
| 문제 해결/상담 | AS/지원 요청     | 장애 신고          | INT-5420  | `quality_satisfaction_score` (품질 만족도), `quality_complaint_score` (품질 불만 Score)                                                                                        | `speed_test_run` (품질/속도 문제 확인 의도), `support_entry` (고객지원 진입), `call_cs_click` (상담사 연결 의도) | `quality_diagnosis_count_5m` (품질 진단 실행 강도), `support_action_count_5m` (즉시 상담 필요 강도)                                                  | Rule   | Rule: Trigger=`speed_test_run=True` 이후 `support_entry=True` 또는 `call_cs_click=True`; Batch=`quality_satisfaction_score`와 `quality_complaint_score`로 장애 의심 baseline 산출; 진단과 상담 행동이 같은 5분 윈도우에서 반복되면 신고 score 상향.                                                                                                                                                                                                            | 장애 접수 필요                                    |
| 관계/공유      | 가족 관리        | 가족결합 관리      | INT-6110  | `family_line_count` (가족 회선 수), `bundle_yn` (결합 여부), `bundle_type` (결합 형태), `bundle_expansion_score` (결합 확장 Score)                                         | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `service_change_count_30d` (상품/서비스 상태 변화 행동 빈도)                              | Model  | Model: 예측 대상=가족결합 추가/유지/변경 가능성; 입력=`family_line_count`, `bundle_yn`, `bundle_type`, `bundle_expansion_score`, `comparison_action_count_5m`, `service_change_count_30d`; 상호작용=가족 회선 수 많음 x 결합 확장 Score 높음 x 서비스 변경 행동; 최종 score=모델 확률값.                                                                                                                                                                     | 가족 결합 추가/유지/변경                          |
| 관계/공유      | 가족 관리        | 자녀 회선 관리     | INT-6120  | `family_line_count` (가족 회선 수), `age` (나이), `bundle_type` (결합 형태)                                                                                                  | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `dominant_entity_5m` (현재 주요 관심 대상)                                                | Rule   | Rule: Trigger=`comparison_action_count_5m>=1`이고 `dominant_entity_5m=family_bundle`이면 적용; Batch=`family_line_count`, `age`, `bundle_type`로 자녀 회선 관리 baseline 산출; 가족 회선 수가 많을수록 score 상향.                                                                                                                                                                                                                                             | 가족 회선 관리 의도                               |
| 관계/공유      | 가족 관리        | 가족 데이터 공유   | INT-6130  | `family_line_count` (가족 회선 수), `remaining_data_ratio` (잔여 데이터 비율), `data_usage_rate` (데이터 사용률)                                                             | -                                                                                                                      | `inquiry_action_count_5m` (정보 확인 강도), `decision_action_count_5m` (납부·변경·가입 실행 의향)                                                  | Rule   | Rule: Trigger=`inquiry_action_count_5m>=1` 이후 `decision_action_count_5m>=1`; Batch=`family_line_count`, `remaining_data_ratio`, `data_usage_rate`로 데이터 공유 필요도 산출; 잔여 데이터가 낮고 가족 회선이 많으면 공유/충전 score 상향.                                                                                                                                                                                                                     | 가족 간 데이터 조정                               |
| 이탈/전환      | 해지 검토        | 위약금 조회        | INT-7110  | `contract_progress_rate` (약정 진행률), `churn_risk_score` (이탈 위험 Score), `cost_burden_score` (비용 부담도)                                                              | -                                                                                                                      | `churn_action_count_5m` (이탈 검토 강도), `dominant_entity_5m` (현재 주요 관심 대상)                                                                 | Model  | Model: 예측 대상=위약금 조회 가능성; 입력=`contract_progress_rate`, `churn_risk_score`, `cost_burden_score`, `churn_action_count_5m`, `dominant_entity_5m`; 상호작용=약정 진행률 높음 x 이탈 검토 행동; 최종 score=모델 확률값.                                                                                                                                                                                                                                | 해지 전 비용 확인                                 |
| 이탈/전환      | 해지 검토        | 해지 절차 확인     | INT-7120  | `churn_risk_score` (이탈 위험 Score), `cost_burden_score` (비용 부담도), `quality_complaint_score` (품질 불만 Score)                                                         | -                                                                                                                      | `churn_action_count_5m` (이탈 검토 강도), `service_change_count_30d` (상품/서비스 상태 변화 행동 빈도)                                               | Rule   | Rule: Trigger=`churn_action_count_5m>=2`; Batch=`churn_risk_score`, `cost_burden_score`, `quality_complaint_score`로 해지 검토 baseline 산출; 최근 `service_change_count_30d`가 있으면 대안 검토 후 해지 절차 확인 맥락으로 보정.                                                                                                                                                                                                                              | 해지 진행 검토                                    |
| 이탈/전환      | 해지 검토        | 해지 상담 요청     | INT-7130  | `churn_risk_score` (이탈 위험 Score), `support_contact_count_30d` (30일 상담 횟수), `quality_complaint_score` (품질 불만 Score)                                              | `call_cs_click` (상담사 연결 의도), `support_entry` (고객지원 진입)                                                | `support_action_count_5m` (즉시 상담 필요 강도), `agent_connect_count_5m` (사람 상담 연결 강도), `churn_action_count_5m` (이탈 검토 강도)          | Model  | Model: 예측 대상=해지 상담 요청 가능성; 입력=`churn_risk_score`, `support_contact_count_30d`, `quality_complaint_score`, `support_entry`, `call_cs_click`, `support_action_count_5m`, `agent_connect_count_5m`, `churn_action_count_5m`; 상호작용=이탈 행동 이후 상담사 연결; 최종 score=모델 확률값.                                                                                                                                                    | 리텐션 대응 필요                                  |
| 이탈/전환      | 비용 절감 검토   | 저가 요금 탐색     | INT-7310  | `price_sensitivity_index` (요금 민감도 Index), `cost_burden_score` (비용 부담도), `monthly_fee` (요금제 월정액)                                                              | -                                                                                                                      | `comparison_action_count_5m` (요금제/혜택/상품 비교 성향), `service_change_count_30d` (상품/서비스 상태 변화 행동 빈도)                              | Model  | Model: 예측 대상=저가 요금제 탐색 가능성; 입력=`price_sensitivity_index`, `cost_burden_score`, `monthly_fee`, `comparison_action_count_5m`, `service_change_count_30d`; 상호작용=비용 부담 높음 x 비교 행동 반복; 최종 score=모델 확률값.                                                                                                                                                                                                                      | 다운셀 또는 비용 절감                             |
| 이탈/전환      | 비용 절감 검토   | 할인 탐색          | INT-7320  | `price_sensitivity_index` (요금 민감도 Index), `membership_engagement_score` (멤버십 활용도), `cost_burden_score` (비용 부담도)                                              | -                                                                                                                      | `inquiry_action_count_5m` (정보 확인 강도), `comparison_action_count_5m` (요금제/혜택/상품 비교 성향)                                                | Model  | Model: 예측 대상=할인/혜택 대안 탐색 가능성; 입력=`price_sensitivity_index`, `membership_engagement_score`, `cost_burden_score`, `inquiry_action_count_5m`, `comparison_action_count_5m`; 상호작용=비용 부담 높음 x 혜택 조회/비교 행동; 최종 score=모델 확률값.                                                                                                                                                                                               | 해지 전 혜택 대안 제시                            |

---

## 6. 추론 흐름

### 6.1. Base Intent 추론

설문 완료 후 Batch Feature만으로 전체 Intent의 baseline score를 만든다. 이 단계는 고객의 정적인 상태와 성향을 반영한다.

예시 입력:

> 30대 / 5년 이상 가입 / 7~9만원 요금제 / 풀 결합 / 가족 4회선 이상 / 영상·게임·SNS 위주 / 데이터 매달 부족 / 청구 급증 없음 / 품질 CS 없음 / 멤버십 3회 이상 / OTT 매일 / 단말 2~3년 / 해외 방문 없음

| Rank | Intent ID | L1             | L2               | L3               | Probability |
| ---- | --------- | -------------- | ---------------- | ---------------- | ----------- |
| 1    | INT-4310  | 혜택/프로모션  | 맞춤 추천 탐색   | AI 추천 탐색     | 15.3%       |
| 2    | INT-2130  | 상품 탐색/가입 | 모바일 상품 탐색 | 데이터 상품 탐색 | 14.8%       |
| 3    | INT-2120  | 상품 탐색/가입 | 모바일 상품 탐색 | 5G 상품 탐색     | 13.4%       |
| 4    | INT-4320  | 혜택/프로모션  | 맞춤 추천 탐색   | 개인화 혜택 탐색 | 12.8%       |
| 5    | INT-4330  | 혜택/프로모션  | 맞춤 추천 탐색   | 추천 요금제 검토 | 11.9%       |
| 기타 | -         | 기타           | n = 108          |                  | 31.8%       |

### 6.2. Real-time Intent 재추론

Step1 또는 Step2 Action이 선택되면 Batch Feature, Event Feature, Behavioral Pattern Feature를 결합해 전체 Intent를 다시 추론한다. 단, Event Feature는 Step1/Step2 선택지만으로 직접 생성되는 목록에 한정한다.

```text
[Step1/Step2 Action 선택]
        |
        +-- 선택 Action 정규화
        |      예: 1-B 요금/청구 상세 페이지 진입
        |          -> selected_step=step1, behavior_event_type=inquiry_action, behavior_entity=billing
        |      예: 2-B2 즉시 납부 버튼 클릭
        |          -> selected_step=step2, parent_action_id=1-B, behavior_event_type=decision_action, behavior_entity=payment
        |
        +-- Behavioral Pattern Feature 갱신
        |      예: step1_menu_count_5m=1, step2_action_count_5m=1, decision_action_count_5m=1
        |
        +-- 직접 Event Feature 생성
        |      예: payment_retry=True, speed_test_run=True, support_entry=True
        |
        +-- Batch + Event + Behavioral Feature 결합
        |
        +-- Rule / Model 추론
        |
        +-- baseline 대비 Probability, Delta, Rank Change 산출
```

### 6.3. 예시 A: Step1 청구 진입 후 Step2 즉시 납부/상담 Intent 상승

| 순서 | 선택 단계 | 선택지                     | behavior_event_type / entity              | 파생 Event Feature                             | Pattern Feature                                                 |
| ---- | --------- | -------------------------- | ----------------------------------------- | ---------------------------------------------- | --------------------------------------------------------------- |
| 1    | Step1     | 요금/청구 상세 페이지 진입 | `inquiry_action` / `billing`          | []                                             | `step1_menu_count_5m=1`, `inquiry_action_count_5m=1`        |
| 2    | Step2     | 청구 상세 항목 조회        | `inquiry_action` / `billing_detail`   | []                                             | `step2_action_count_5m=1`, `inquiry_action_count_5m=2`      |
| 3    | Step2     | 즉시 납부 버튼 클릭        | `decision_action` / `payment`         | `payment_retry=True`                         | `decision_action_count_5m=1`, `payment_retry_count_5m=1`    |
| 4    | Step2     | 즉시 납부 버튼 재클릭      | `decision_action` / `payment`         | `payment_retry=True`                         | `payment_retry_count_5m=2`, `same_entity_repeat_count_5m=2` |
| 5    | Step1     | 고객지원 페이지 진입       | `support_action` / `customer_support` | `support_entry=True`                         | `step1_menu_count_5m=2`, `support_action_count_5m=1`        |
| 6    | Step2     | 전화 상담 연결 클릭        | `support_action` / `support_consult`  | `support_entry=True`, `call_cs_click=True` | `support_action_count_5m=2`, `agent_connect_count_5m=1`     |

| Rank | L1             | L2             | L3             | 변화                                      |
| ---- | -------------- | -------------- | -------------- | ----------------------------------------- |
| 1    | 셀프처리       | 요금/납부 처리 | 즉시 납부      | 즉시 납부 선택과 결제 재시도로 상승       |
| 2    | 문제 해결/상담 | 결제 오류 해결 | 결제 오류 해결 | 납부 재시도 반복과 상담사 연결로 상승     |
| 3    | My 정보 조회   | 청구 조회      | 청구 상세 조회 | 청구 상세 조회와 납부 행동으로 상승       |
| 4    | My 정보 조회   | 청구 조회      | 미납 요금 조회 | 납부 시도 전후 미납 상태 확인 필요로 상승 |
| 5    | 셀프처리       | 요금/납부 처리 | 자동이체 변경  | 자동납부 설정 변경 행동이 있으면 상승     |

### 6.4. 예시 B: Step1 고객지원 진입 후 Step2 WiFi 진단/상담 Intent 상승

| 순서 | 선택 단계 | 선택지                       | behavior_event_type / entity                  | 파생 Event Feature                             | Pattern Feature                                                                          |
| ---- | --------- | ---------------------------- | --------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| 1    | Step1     | 고객지원 페이지 진입         | `support_action` / `customer_support`     | `support_entry=True`                         | `step1_menu_count_5m=1`, `support_action_count_5m=1`                                 |
| 2    | Step2     | WiFi 진단 / 속도 측정 실행   | `diagnostic_action` / `quality_diagnosis` | `speed_test_run=True`                        | `step2_action_count_5m=1`, `diagnostic_action_count_5m=1`, `speed_test_count_5m=1` |
| 3    | Step2     | WiFi 진단 / 속도 측정 재실행 | `diagnostic_action` / `quality_diagnosis` | `speed_test_run=True`                        | `diagnostic_action_count_5m=2`, `speed_test_count_5m=2`                              |
| 4    | Step2     | 챗봇 상담 진입               | `support_action` / `chatbot`              | `support_entry=True`, `chatbot_start=True` | `support_action_count_5m=2`, `support_after_diagnosis=true`                          |
| 5    | Step2     | 전화 상담 연결 클릭          | `support_action` / `support_consult`      | `support_entry=True`, `call_cs_click=True` | `support_action_count_5m=3`, `agent_connect_count_5m=1`                              |

| Rank | L1             | L2             | L3             | 변화                                    |
| ---- | -------------- | -------------- | -------------- | --------------------------------------- |
| 1    | 문제 해결/상담 | 품질 문제 해결 | WiFi 문제 해결 | WiFi 진단 선택과 속도측정 반복으로 상승 |
| 2    | 문제 해결/상담 | 품질 문제 해결 | 속도 저하 해결 | 속도측정 실행 반복으로 상승             |
| 3    | 문제 해결/상담 | AS/지원 요청   | 장애 신고      | 진단 이후 상담 전환으로 상승            |
| 4    | 문제 해결/상담 | 고객 상담      | 전화 상담      | 챗봇 이후 전화 상담 연결로 상승         |
| 5    | 문제 해결/상담 | 품질 문제 해결 | QoE 문제 해결  | OTT 이용 고객의 속도측정 반복으로 상승  |

### 6.5. 예시 C: Step1 가입정보 진입 후 Step2 위약금/해지 Intent 상승

| 순서 | 선택 단계 | 선택지                  | behavior_event_type / entity               | 파생 Event Feature                             | Pattern Feature                                                |
| ---- | --------- | ----------------------- | ------------------------------------------ | ---------------------------------------------- | -------------------------------------------------------------- |
| 1    | Step1     | 가입정보 페이지 진입    | `inquiry_action` / `subscription_info` | []                                             | `step1_menu_count_5m=1`, `inquiry_action_count_5m=1`       |
| 2    | Step2     | 위약금 계산 페이지 진입 | `churn_action` / `penalty`             | []                                             | `step2_action_count_5m=1`, `churn_action_count_5m=1`       |
| 3    | Step2     | 해지 신청 페이지 진입   | `churn_action` / `cancel`              | []                                             | `churn_action_count_5m=2`, `same_entity_repeat_count_5m=1` |
| 4    | Step1     | 고객지원 페이지 진입    | `support_action` / `customer_support`  | `support_entry=True`                         | `step1_menu_count_5m=2`, `support_action_count_5m=1`       |
| 5    | Step2     | 전화 상담 연결 클릭     | `support_action` / `support_consult`   | `support_entry=True`, `call_cs_click=True` | `support_action_count_5m=2`, `agent_connect_count_5m=1`    |

| Rank | L1        | L2        | L3             | 변화                          |
| ---- | --------- | --------- | -------------- | ----------------------------- |
| 1    | 이탈/전환 | 해지 검토 | 위약금 조회    | 위약금 계산 행동으로 상승     |
| 2    | 이탈/전환 | 해지 검토 | 해지 절차 확인 | 해지 페이지 진입으로 상승     |
| 3    | 이탈/전환 | 해지 검토 | 해지 상담 요청 | 해지 흐름 후 상담 연결로 상승 |

---

## 7. Customer Context 저장 및 활용

### 7.1. Customer Context Library 적재

Context Library에는 최종 추론 결과와 evidence를 저장한다. 시연 화면에서 보여주는 baseline, delta, rank_change는 "행동 전/후 재추론 결과 비교"로 산출한다.

| 필드                               | 레벨     | 데이터 타입                  | 예시 값                          | 설명                                                     |
| ---------------------------------- | -------- | ---------------------------- | -------------------------------- | -------------------------------------------------------- |
| `cust_id`                        | Context  | string                       | `A001`                         | 고객 ID                                                  |
| `session_id`                     | Context  | string                       | `S20260707-001`                | 시연 세션 ID                                             |
| `scenario_id`                    | Context  | string                       | `cs-myk-v3`                    | 시나리오 ID                                              |
| `created_at`                     | Context  | datetime/string              | `2026-07-07T14:30:00+09:00`    | Context 생성 시각                                        |
| `expired_at`                     | Context  | datetime/string              | `2026-07-07T15:00:00+09:00`    | Context 만료 시각                                        |
| `intent_id`                      | Intent   | string                       | `INT-3110`                     | Intent ID                                                |
| `intent_nm_ko`                   | Intent   | string                       | `즉시 납부`                    | Intent 한글명                                            |
| `L1`                             | Intent   | string enum                  | `셀프처리`                     | L1 Intent 분류                                           |
| `L2`                             | Intent   | string enum                  | `요금/납부 처리`               | L2 Intent 분류                                           |
| `version`                        | Intent   | string                       | `1.0.0`                        | Intent Metadata 버전                                     |
| `inference_type`                 | Intent   | string enum                  | `Rule`                         | `Rule` 또는 `Model`                                  |
| `score`                          | Intent   | float                        | `0.91`                         | Batch + Event + Pattern 결합 점수                        |
| `rank`                           | Intent   | integer                      | `1`                            | 최종 순위                                                |
| `evidence`                       | Evidence | array `<object>`           | `[{...}]`                      | score 산출 근거 묶음                                     |
| `evidence.rule_id`               | Evidence | string/null                  | `RULE-CS-3110-001`             | Rule 기반 추론이면 Rule ID, Model이면 null 또는 Model ID |
| `evidence.features`              | Evidence | array `<object>`           | `[{ "source": "event", ... }]` | score에 기여한 Feature 목록                              |
| `evidence.features.source`       | Evidence | string enum                  | `batch`                        | `batch`, `event`, `behavior` 중 하나               |
| `evidence.features.feature`      | Evidence | string                       | `payment_retry`                | Feature 명                                               |
| `evidence.features.actual_value` | Evidence | integer/float/boolean/string | `True`                         | 추론 시점의 실제 Feature 값                              |

예시:

```json
{
  "cust_id": "A001",
  "session_id": "S20260707-001",
  "scenario_id": "cs-myk-v3",
  "created_at": "2026-07-07T14:30:00+09:00",
  "expired_at": "2026-07-07T15:00:00+09:00",
  "intent_id": "INT-3110",
  "intent_nm_ko": "즉시 납부",
  "L1": "셀프처리",
  "L2": "요금/납부 처리",
  "version": "1.0.0",
  "inference_type": "Rule",
  "score": 0.91,
  "rank": 1,
  "evidence": [
    {
      "rule_id": "RULE-CS-3110-001",
      "features": [
        { "source": "batch", "feature": "cost_burden_score (비용 부담도)", "actual_value": 0.72 },
        { "source": "event", "feature": "payment_retry", "actual_value": true },
        { "source": "behavior", "feature": "payment_retry_count_5m", "actual_value": 2 },
        { "source": "behavior", "feature": "agent_connect_count_5m", "actual_value": 1 }
      ]
    }
  ]
}
```

### 7.2. 활용 방안

| L1             | L3             | App Push                          | 고객센터 Context                                  | Agent                                      |
| -------------- | -------------- | --------------------------------- | ------------------------------------------------- | ------------------------------------------ |
| My 정보 조회   | 청구 상세 조회 | 청구 상세 내역을 확인해주세요     | 청구 상세 조회와 납부 재시도 행동을 함께 확인     | 요금 변동 내역을 정리해드릴까요?           |
| 셀프처리       | 즉시 납부      | 지금 바로 납부할 수 있습니다      | 즉시 납부 버튼 클릭과 납부 재시도 횟수 확인       | 가장 빠른 납부 방법을 안내해드릴까요?      |
| 문제 해결/상담 | 결제 오류 해결 | 결제 도움말을 확인해보세요        | 납부 재시도 반복과 전화 상담 연결 evidence 제공   | 납부 과정을 함께 확인해드릴까요?           |
| 문제 해결/상담 | 챗봇 상담      | 챗봇 상담으로 빠르게 확인해보세요 | 챗봇 상담 진입과 고객지원 진입 evidence 제공      | 챗봇으로 먼저 확인해드릴까요?              |
| 문제 해결/상담 | 속도 저하 해결 | 속도측정을 실행해보세요           | 속도측정 실행과 품질 진단 반복 evidence 제공      | 속도 저하 원인을 확인해드릴까요?           |
| 이탈/전환      | 해지 상담 요청 | 해지 전 대안을 확인해보세요       | 위약금/해지 페이지 행동과 상담 연결 evidence 제공 | 해지 전 비용과 대안을 함께 비교해드릴까요? |

---

## 8. 후속 코드 반영 원칙

문서 확정 후 코드 수정은 아래 순서로 진행한다.

1. `scenarios/cs-myk-v3/intents.json`에 `batch_features`, `event_features`, `behavioral_features`, `method_detail`을 추가한다.
2. Event Extractor를 Step1/Step2 직접 생성 Event Feature 기반으로 재설계한다.
3. Behavioral Pattern Extractor를 Step1/Step2 선택 행동의 반복, 전환, 진단, 상담, 이탈 행동 카운트 중심으로 재설계한다.
4. Batch Builder의 Index/Score 정의가 문서와 맞는지 검증하고 필요한 산식을 보정한다.
5. Rule/Model 구현은 현재 코드가 아니라 이 문서의 방법론 상세를 기준으로 수정한다.
6. 검증 스크립트는 아래를 확인해야 한다.
   - 문서/JSON의 Batch Feature는 모두 생성 가능해야 한다.
   - Event Feature는 Step1/Step2 선택지만으로 직접 생성 가능해야 한다.
   - Behavioral Feature는 단일 이벤트가 아니라 누적/반복/순서 기반이어야 한다.
   - Model 학습 Feature와 JSON Feature는 일치해야 한다.
   - 핵심 시연 흐름에서 관련 Intent의 score/rank 변화가 설명 가능해야 한다.

---

## 9. Assumptions

* 영어 feature name은 snake_case를 사용한다.
* Batch Feature는 Base Feature, Index Feature, Score Feature로 구분한다.
* Base Feature는 `base`, `delta`, `ratio` 타입으로 세분화한다.
* `base`는 설문/KFM/SGI 원천값, 인코딩값, 또는 시연 proxy 기본값이다.
* `delta`는 이전 시점 대비 증감률처럼 단순 사칙연산으로 산출되는 변화량 Feature다.
* `ratio`는 사용률, 잔여율, 약정 진행률처럼 단순 비율 또는 비율형 proxy Feature다.
* Index Feature는 Base Feature를 집계하거나 정규화하여 만든 고객 상태 지표다.
* Score Feature는 Intent 최종 score가 아니라 Batch Feature의 한 종류다.
* Score Feature는 Base Feature와 Index Feature를 입력으로 구체적인 Rule 또는 Model 로직을 적용해 만든 예측성 Batch Feature다.
* Intent별 최종 score 산출 방식은 Section 5의 `방법론 상세`에 작성한다.
* Intent별 최종 score는 Batch Feature(Base/Index/Score), Event Feature, Behavioral Pattern Feature를 조합해 산출한다.
* 시연의 Step1/Step2 선택지는 사용자가 다음에 고르는 행동 원천이며, Event Feature는 Step1/Step2 선택 행동 자체가 Trigger인 경우에만 생성한다.
* 현재 문서는 Step1/Step2 선택지만으로 직접 생성되는 Event Feature만 사용한다.
* 설문은 13문항을 유지한다.
* 문서 확정 후 코드 구현은 이 Feature/Index/Score 정의와 Intent score 산출식을 기준으로 맞춘다.
