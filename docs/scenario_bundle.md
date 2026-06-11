## 20260608

## 0. 시나리오 개요

### 시연 컨셉

* 결합 상품 활성화를 위해 **설문 기반 고객 정보**와 **앱 내 실시간 행동**을 결합하여 고객별 Intent를 추론하고, 채널별 맞춤 Action으로 연결하는 시연

**→ 동일한 고객이라도 실시간 행동에 따라 Intent 우선순위가 변화**하며, 이에 따라 **앱 Push·고객센터·Agent에서 제공되는 메세지와 서비스가 달라지는 과정을 체험형으로 확인**

## 1. Intent Taxonomy

### **1.1. 결합 Domain Intent Taxonomy**

* 결합 서비스는 단순 상품 가입뿐 아니라 할인 최적화, 회선 확장, 재약정, 해지 방어 등 다양한 고객 목적 포함
  * 따라서 Intent Taxonomy는 상품이나 요금제 중심이 아닌 **고객이 특정 시점에 수행하려는 목적과 업무**를 기준으로 설계
    * L1 : 고객 Lifecycle 및 사업 목적 관점의 Intent 유형
      * 가입 확대 : 결합 가입 가능성과 적합한 상품을 탐색하려는 의도(결합 가능 여부, 상품 탐색, 가입 혜택)
      * 할인 최적화 : 더 많은 할인과 혜택을 확보하려는 의도(총액결합, 할인 확대)
      * 회선/서비스 확장 : 결합 대상 회선이나 서비스를 확대하려는 의도(가족회선, 인터넷, IPTV, 홈WiFi)
      * 유지/락인 : 현재 결합의 우지 가치를 확인하려는 의도(재약정, 장기고객 혜택)
      * 이탈 검토 : 해지 또는 타사 이동 여부를 검토하려는 의도(위약금, 번호이동, 타사 비교)
    * L2 : 고객이 수행하려는 업무(Task)
    * L3 : 고객이 실제 확인·판단·의사결정하려는 세부 Intent

→ 동일한 서비스라도 고객의 현재 상황과 목적에 따라 서로 다른 Intent를 추론하고, 이후 추천·Agent·검색·마케팅 등의 Action으로 연결할 수 있도록 구성

### 1.2. Intent Taxonomy Metadata 정의

* 각 Intent(L3)에 대해 추론에 필요한 Feature 정보와 추론 방식(Rule, Model)을 정의한 Metadata 구축

| **구분**            | **추론 방법론**                                                                 | **적용 기준**                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Rule-Based Intent Trigger | Feature 조건식 및 Event Trigger 기반 추론                                             | 자격 여부, 상태 확인, 특정 Action 발생 자체가 Intent를 의미하는 경우                                     |
| Predictive Intent Model   | Batch Feature + Event Feature + Behavioral Pattern Feature 기반 Binary Classification | 복수 Feature 조합을 통해 고객의 관심도·선호도·가입 가능성·이탈 가능성을 확률적으로 추정해야 하는 경우 |

* Output : Intent Taxonomy Metadata

| **L0**                            | **L1**                                                                                    | **L2**                                                                                                                                                           | **L3**                                                                                                                                                                                                                                    | **Batch Feature**                                                                                                                                        | **Event Feature**                                                                                                                                                                                                                                  | **Behavioral Pattern Feature**                                                                       | **방법론** |
| --------------------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------- |
| 결합                                    | 가입 확대* 신규 결합 유치                                                                       | 결합 가능 여부 탐색                                                                                                                                                    | 가족 결합 가능 여부 확인 ``인터넷/IPTV 결합 가능 여부 확인``현재 요금제 기반 결합 가능 여부 확인                                                                                                                                                | Bundle Opportunity Index, Bundle Preference Index, family_line_countHome Service Interest Index, bundle_service_countplan_tier, Bundle Opportunity Index       | ---                                                                                                                                                                                                                                                      | entity_focus_ratio_5m, dominant_entity_5mexplored_entity_count_5m, dominant_entity_5mentity_focus_ratio_5m | RuleRuleRule     |
| 결합 상품 탐색                          | 할인 중심 결합 상품 탐색 ``데이터 혜택 중심 결합 상품 탐색``프리미엄 혜택 중심 결합 상품 탐색   | Discount Optimization Score, Cost Orientation Indexcontent_consumption_type, Acquisition Scoreplan_tier, Benefit Engagement Index                                      | ---                                                                                                                                                                                                                                             | comparison_action_count_5m, dominant_entity_5mexplored_entity_count_5mexplored_entity_count_5m                                                                 | ModelModelModel                                                                                                                                                                                                                                          |                                                                                                            |                  |
| 가입 혜택 탐색                          | 신규 가입 혜택 확인                                                                             | Acquisition Score, Cost Orientation Index                                                                                                                              | -                                                                                                                                                                                                                                               | comparison_action_count_5m                                                                                                                                     | Model                                                                                                                                                                                                                                                    |                                                                                                            |                  |
| 가입 실행 검토                          | 온라인 가입 검토 ``상담 기반 가입 검토``매장 방문 가입 검토                                     | Acquisition ScoreAcquisition ScoreAcquisition ScoreAcquisition Score                                                                                                   | bundle_apply_submitsupport_entrysupport_entry-                                                                                                                                                                                                  | decision_action_count_5m, action_intensity_5mdecision_action_count_5mexplored_entity_count_5mexplored_entity_count_5m                                          | ModelModelModelRule                                                                                                                                                                                                                                      |                                                                                                            |                  |
| 할인 최적화* 결합 전환/혜택 강화        | 현재 혜택 점검                                                                                  | 현재 적용 혜택 확인                                                                                                                                                    | Benefit Engagement Index                                                                                                                                                                                                                        | -                                                                                                                                                              | explored_entity_count_5m, last_entity                                                                                                                                                                                                                    | Rule                                                                                                       |                  |
| 추가 혜택 탐색                          | 추가 할인 가능 여부 확인 ``프로모션/이벤트 혜택 탐색``카드 제휴 혜택 탐색                       | Benefit Engagement IndexDiscount Optimization Score, Cost Orientation IndexBenefit Engagement IndexCost Orientation Index                                              | ------                                                                                                                                                                                                                                          | entity_focus_ratio_5mcomparison_action_count_5mexplored_entity_count_5mdominant_entity_5m, last_entity                                                         | RuleModelModelRule                                                                                                                                                                                                                                       |                                                                                                            |                  |
| 혜택 활용 최적화                        | 데이터 혜택 활용 검토 ``멤버십 혜택 활용 검토``OTT/콘텐츠 혜택 활용 검토``미사용 혜택 확인      | Benefit Engagement IndexBenefit Engagement Index, benefit_utilizationcontent_consumption_type, Benefit Engagement IndexBenefit Engagement Index, benefit_utilization   | ----                                                                                                                                                                                                                                            | explored_entity_count_5mexplored_entity_count_5mexplored_entity_count_5mentity_focus_ratio_5m, dominant_entity_5m                                              | ModelModelModelRule                                                                                                                                                                                                                                      |                                                                                                            |                  |
| 회선/서비스 확장* 가족/디바이스/홈 확장 | 결합 범위 확대                                                                                  | 가족 회선 추가 검토 ``인터넷 결합 추가 검토``IPTV 결합 추가 검토 ``인터넷+IPTV 통합 이용 검토``홈 WiFi 추가 검토                                                       | Bundle Expansion Score, family_line_count``Home Service Interest IndexHome Service Interest Index, content_consumption_typeHome Service Interest Index, bundle_service_countHome Service Interest Indexhousehold_change, Bundle Expansion Score | -----``-                                                                                                                                                       | entity_focus_ratio_5m, dominant_entity_5m``explored_entity_count_5m, dominant_entity_5mexplored_entity_count_5m, dominant_entity_5mexplored_entity_count_5m, entity_transition_patternentity_focus_ratio_5m, dominant_entity_5mentity_transition_pattern | Model``ModelModelModelModelRule                                                                            |                  |
| 디바이스/IoT 확장                       | 워치 회선 추가 검토 ``태블릿 결합 추가 검토``세컨드 디바이스 연결 검토``IoT 기기 연계 검토      | Bundle Expansion Score, plan_tierBundle Expansion Score, plan_tierBundle Expansion Score, content_consumption_typeBundle Expansion Score, content_consumption_type     | ----                                                                                                                                                                                                                                            | explored_entity_count_5m, action_intensity_5mexplored_entity_count_5m, action_intensity_5mexplored_entity_count_5mexplored_entity_count_5m                     | ModelModelModelModel                                                                                                                                                                                                                                     |                                                                                                            |                  |
| 결합 구조 재구성                        | 가족 회선 통합 검토 ``가족 회선 분리 검토``명의 변경 검토 ``대표 회선 변경 검토``회선 이동 검토 |                                                                                                                                                                        |                                                                                                                                                                                                                                                 |                                                                                                                                                                |                                                                                                                                                                                                                                                          |                                                                                                            |                  |
| 유지/락인* 장기 유지/재약정             | 재약정 검토                                                                                     | 약정 상태 및 연장 혜택 확인``재약정 혜택 비교                                                                                                                          | Retention Propensity Score, Retention Orientation Index, tenure_groupRetention Propensity Score, Benefit Engagement Index                                                                                                                       | -renewal_consult_submit                                                                                                                                        | explored_entity_count_5mcomparison_action_count_5m, decision_action_count_5m, dominant_entity_5m                                                                                                                                                         | RuleModel                                                                                                  |                  |
| 장기 고객 혜택 확인                     | 장기 혜택 확인                                                                                  |                                                                                                                                                                        |                                                                                                                                                                                                                                                 |                                                                                                                                                                |                                                                                                                                                                                                                                                          |                                                                                                            |                  |
| 결합 유지 영향 확인                     | 요금제 변경 영향 확인``결합 해지 영향 확인                                                      |                                                                                                                                                                        |                                                                                                                                                                                                                                                 |                                                                                                                                                                |                                                                                                                                                                                                                                                          |                                                                                                            |                  |
| 이탈 검토* 해지 고려                    | 경쟁사 비교                                                                                     | 타사 결합 혜택/가격 비교``번호이동 기반 혜택 비교                                                                                                                      | Churn Risk Score, Cost Orientation IndexChurn Risk Score, Cost Orientation Index                                                                                                                                                                | competitor_compare_entrymnp_benefit_check                                                                                                                      | comparison_action_count_5m, churn_action_count_5m, dominant_entity_5mcomparison_action_count_5m, churn_action_count_5m, last_entity                                                                                                                      | ModelModel                                                                                                 |                  |
| 혜택/비용 불만                          | 혜택 부족 체감 ``결합 유지 가치 하락``통신비 부담 증가                                          | Cost Orientation Index, dissatisfaction_factor, Churn Risk ScoreChurn Risk Score, Retention Propensity ScoreCost Orientation Index, cost_sensitivity, Churn Risk Score | ---                                                                                                                                                                                                                                             | churn_action_count_5m, dominant_entity_5mcomparison_action_count_5m, churn_action_count_5mcomparison_action_count_5m, churn_action_count_5m                    | ModelModelModel                                                                                                                                                                                                                                          |                                                                                                            |                  |
| 품질 불만                               | 인터넷 품질 불만 ``IPTV 품질 불만``모바일 데이터 품질 불만``장애 반복 불만                      | dissatisfaction_factor, Churn Risk Scoredissatisfaction_factor, Churn Risk Scoredissatisfaction_factor, Churn Risk Scoredissatisfaction_factor, Churn Risk Score       | support_entrysupport_entrysupport_entrysupport_entry                                                                                                                                                                                            | churn_action_count_5mchurn_action_count_5mchurn_action_count_5mentity_focus_ratio_5m, churn_action_count_5m                                                    | ModelModelModelModel                                                                                                                                                                                                                                     |                                                                                                            |                  |
| 해지 검토                               | 해지 절차 확인 ``위약금 확인``해지 영향 확인``번호이동 절차 확인                                | Churn Risk ScoreChurn Risk ScoreChurn Risk Score, Retention Propensity ScoreChurn Risk Score                                                                           | -termination_penalty_check-mnp_benefit_check                                                                                                                                                                                                    | explored_entity_count_5m, last_entitychurn_action_count_5m, last_entitycomparison_action_count_5m, entity_transition_patternchurn_action_count_5m, last_entity | RuleRuleRuleRule                                                                                                                                                                                                                                         |                                                                                                            |                  |

---

## 2. 배치 데이터 생성

### 2.1. 질문&답변

* 질문은 고객의 현재 상태와 이용 성향을 파악하기 위한 목적으로 구성
  * 고객 상태 정보(Q1~Q6)는 가입 상품, 이용 기간, 가족 구성 등 비교적 변화가 적은 특성 수집
  * 이용 성향 정보(Q7~Q10)는 비용 민감도, 혜택 활용 성향, 서비스 이용 방식 등 고객의 관심사와 의사결정 특성을 파악하는 데 활용

| **질문 번호** | **구분** | **질문**                                                                                                                                                                                     | **질문 번호** | **구분** | **질문**                                                                                              |
| ------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | -------------- | ----------------------------------------------------------------------------------------------------------- |
| 1                   | 고객 상태 정보 | 기본 정보를 선택해주세요.* 성별 : 남성 / 여성* 연령대 : 10대 이하 / 20대 / 30대 / 40대 / 50대 / 60대 이상* 현재 사용 중인 요금제 : 5G 프리미어급 / 5G 중간요금제 / 5G 슬림급 / LTE 요금제 / 알뜰폰 | 7                   | 이용 성향      | 현재 월 통신비는 어느 수준인가요?* 5만원 미만* 5만원 이상~7만원 미만* 7만원 이상 ~ 10만원 미만* 10만원 이상 |
| 2                   | 고객 상태 정보 | 가족 중 KT를 이용하는 사람은?·* 나만 이용* 1~2명 더 이용* 3명 이상 더 이용                                                                                                                        | 8                   | 이용 성향      | 평소 혜택이나 쿠폰 이용 수준은?* 거의 사용하지 않는다* 필요한 것만 사용한다* 자주 찾아서 사용한다           |
| 3                   | 고객 상태 정보 | 현재 이용 중인 서비스는?* 모바일* 모바일 + 인터넷* 모바일 + 인터넷 + IPTV                                                                                                                          | 9                   | 이용 성향      | 현재 가장 아쉽게 느끼는 부분은?* 통신비* 혜택* 인터넷 품질* IPTV 품질* 모바일 데이터 품질* 없음             |
| 4                   | 고객 상태 정보 | 최근 1년 내 가족 또는 거주 환경 변화가 있었나요?* 변화 없음* 이사·독립* 가족 구성원 증가                                                                                                          | 10                  | 이용 성향      | 콘텐츠를 시청한다면 주로 어떤 방식인가요?* TV 위주* OTT 위주* 둘 다 이용* 콘텐츠 이용이 많지 않음           |
| 5                   | 고객 상태 정보 | 현재 KT 이용 기간은 어느 정도인가요?* 1년 미만* 1~3년* 3년 이상                                                                                                                                    |                     |                |                                                                                                             |
| 6                   | 고객 상태 정보 | 현재 약정 상태는?* 약정 없음* 약정 잔여 6개월 이상* 약정 만료 예정(6개월 이내)                                                                                                                     |                     |                |                                                                                                             |

### 2.2. Batch Context Feature Builder

* 질문을 통해 수집한 고객의 장기·중기 상태 및 속성을 기반으로 Batch Context Feature 생성
* 예시 Output :  Batch Feature Table = (1) Base Feature + (2) Index + (3) Score

(1) Base Feature : 고객 상태·행동을 표현하는 원천/집계 기반 데이터

| **항목**           | **사용 Feature** | **의미**            |
| ------------------------ | ---------------------- | ------------------------- |
| gender                   | Q1                     | 성별                      |
| age_group                | Q1                     | 연령대                    |
| plan_tier                | Q1                     | 사용 요금제               |
| family_line_count        | Q2                     | KT 이용 가족 수           |
| subscribed_service_count | Q3                     | 현재 이용 서비스 수       |
| household_change         | Q4                     | 최근 가족·주거 환경 변화 |
| tenure_group             | Q5                     | KT 이용 기간              |
| contract_status          | Q6                     | 현재 약정 상태            |
| montly_bill_level        | Q7                     | 월 통신비 수준            |
| benefit_utilization      | Q8                     | 혜택 활용 성향            |
| dissatisfaction_factor   | Q9                     | 주요 불만 요인            |
| content_view_mode        | Q10                    | 콘텐츠 소비 방식          |

(2) Index : 다수 feature를 정규화·집계하여 고객 상태·강도·우선순위를 공통 스케일(0~100)로 표현한 지표

| Index                        | 사용 Feature                                                  | 생성 Rule                                                | 의미                          |
| ---------------------------- | ------------------------------------------------------------- | -------------------------------------------------------- | ----------------------------- |
| Bundle Opportunity Index     | family_line_count, subscribed_service_count, household_change | 가족 수↑, 이용 서비스 수↓, 가족 구성 변화 존재 시 증가 | 결합 확대 가능성              |
| Benefit Optimization Index   | plan_tier, monthly_bill_level, benefit_utilization            | 요금제 대비 통신비 수준↑, 혜택 활용도↓일수록 증가      | 추가 할인·혜택 최적화 필요성 |
| Home Service Expansion Index | subscribed_service_count, content_view_mode, household_change | 콘텐츠 이용↑, 홈서비스 미가입일수록 증가                | 인터넷/IPTV 확장 가능성       |
| Retention Index              | tenure_group, contract_status                                 | 이용기간↑, 약정 만료 임박 시 증가                       | 유지·재약정 가능성           |
| Churn Risk Index             | dissatisfaction_factor, contract_status                       | 불만 존재, 약정 만료 임박 시 증가                        | 잠재 이탈 위험도              |
| Benefit Engagement Index     | benefit_utilization                                           | 혜택 활용 수준이 높을수록 증가                           | 혜택 활용 적극성              |

(3) Score : Feature·Index 기반 ~ML/DL 예측 점수~ **(현재는 rule로 정의)**

| **항목**              | **사용 Feature**                                                         | **생성 Rule**                                                                 | **의미**          |
| --------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- | ----------------------- |
| Acquisition Score           | Bundle Opportunity Index, Home Service Interest Index                          | 0.6 × Bundle Opportunity + 0.4 × Home Service Interest                            | 신규결합 가입 가능성    |
| Discount Optimization Score | Cost Orientation Index, Benefit Engagement Index                               | 0.6 × Cost Orientation + 0.4 × Benefit Engagement                                 | 할인최적화 가능성       |
| Bundle Expansion Score      | Bundle Opportunity Index, Bundle Preference Index, Home Service Interest Index | 0.4 × Bundle Opportunity + 0.3 × Bundle Preference + 0.3 × Home Service Interest | 결합·서비스확장 가능성 |
| Retention Propensity Score  | Retention Orientation Index, Benefit Engagement Index                          | 0.7 × Retention Orientation + 0.3 × Benefit Engagement                            | 유지·재약정가능성      |
| Churn Risk Score            | Cost Orientation Index, dissatisfaction_factor                                 | 비용불만 및 서비스 불만이 높을수록 증가                                             | 이탈 위험도             |

### 2.3. Base Intent 추론

* Batch Feature를 활용하여 L3 Intent의 초기 Intent Score 산정
  * Rule 기반 추론은 사전 정의된 조건식을 통해 Score 계산
  * 모델 기반 추론은 현재 활용 가능한 Batch Feature만을 입력값으로 사용하여 Score 계산
* 두 방법론을 통해 산정된 Intent Score를 정규화한 후, 최종 Intent Score를 기반으로 Base Intent Top-K 생성
* 예시 Output : Customer Intent Score

| **Rank** | **L1**     | **L2**        | **L3**             | **Score** | **Probability** |
| -------------- | ---------------- | ------------------- | ------------------------ | --------------- | --------------------- |
| 1              | 할인 최적화      | 추가 혜택 탐색      | 추가 할인 가능 여부 확인 | 87              | 26.1%                 |
| 2              | 할인 최적화      | 결합 할인 확대 검토 | 총액결합 할인 확대 검토  | 81              | 24.3%                 |
| 3              | 유지/락인        | 재약정 검토         | 재약정 혜택 비교         | 68              | 20.4%                 |
| 4              | 회선/서비스 확장 | 홈서비스 확장       | IPTV 결합 추가 검토      | 52              | 15.6%                 |
| 5              | 가입 확대        | 결합 상품 탐색      | 할인 중심 결합 상품 탐색 | 45              | 13.5%                 |

## 3. 실시간 행동 데이터 생성

### 3.1. 앱 행동 선택지

| **Step1 (목적형 행동)**  | **Step2 (세부 행동)** | **Step1 (목적형 행동)** | **Step2 (세부 행동)** |
| ------------------------------ | --------------------------- | ----------------------------- | --------------------------- |
| **할인 혜택 확인**       | 할인 계산기 조회            | **약정 혜택 확인**      | 약정 상태 조회              |
| 카드 제휴 혜택 조회            | 현재 결합 혜택 조회         |                               |                             |
| 미사용 혜택 조회               | 재약정 혜택 조회            |                               |                             |
| 장기고객 혜택 조회             | 재약정 상담 신청            |                               |                             |
| **결합 할인 확인**       | 가족 결합 조회              | **타사 혜택 비교**      | 타사 결합 할인 비교         |
| 총액결합 할인 조회             | 번호이동 혜택 조회          |                               |                             |
| 결합 가능 여부 조회            | 인터넷 신규가입 혜택 조회   |                               |                             |
| 결합 가입/변경 신청            | 위약금 조회                 |                               |                             |
| **인터넷/IPTV 알아보기** | 인터넷 상품 조회            | 고객센터 상담 연결            |                             |
| IPTV 상품 조회                 |                             |                               |                             |
| 인터넷+IPTV 결합 조회          |                             |                               |                             |
| 홈WiFi 조회                    |                             |                               |                             |

### **3.2. Event Feature Extractor**

* 시연자의 앱 행동 선택 결과 중 단일 클릭만으로 즉시 확인/대응이 필요한 Action만 필터링

| **카테고리** | **event_type**      | **Trigger Action** |
| ------------------ | ------------------------- | ------------------------ |
| 고객지원           | support_entry             | 고객센터 상담 연결       |
| 가입상태 변경      | bundle_apply_submit       | 결합 가입/변경 신청      |
| 계약상태 변경      | renewal_consult_submit    | 재약정 상담 신청         |
| 이탈 위험          | competitor_compare_entry  | 타사 혜택 비교           |
| 이탈 위험          | mnp_benefit_check         | 번호이동 혜택 조회       |
| 이탈 위험          | termination_penalty_check | 위약금 조회              |

* 예시 Output : Event Feature Table

| event_ts | session_id | cust_id | event_type                | event_value |
| -------- | ---------- | ------- | ------------------------- | ----------- |
| 12:01    | S001       | A001    | support_entry             | True        |
| 12:03    | S002       | A002    | termination_penalty_check | True        |
| 12:04    | S003       | A003    | mnp_benefit_check         | True        |
| 12:05    | S004       | A004    | competitor_compare_entry  | True        |
| 12:06    | S005       | A005    | bundle_apply_submit       | True        |

### 3.3. Behavioral Pattern Extractor

* 사용자가 선택한 Action을 기반으로 생성된 실시간 행동 데이터를 활용하여 Behavioral Feature로 생성하는 단계
  * 행동 유형(event_type)과 탐색 대상(entity)를 기준으로 반복·실패·재시도·전환 흐름 등을 aggregation
  * 기존에는 event_type이 앱의 메뉴 계위에 해당하였으나, 시연에서는 탐색 깊이 제한이 있음에 따라 임시 type 정의

| **event_type** | **의미**               |
| -------------------- | ---------------------------- |
| action_select        | 일반 탐색 행동               |
| comparison_action    | 비교성 행동                  |
| decision_action      | 가입·변경·재약정 신청 행동 |
| churn_action         | 이탈 관련 행동               |

| **entity**   | **해당 Action** |
| ------------------ | --------------------- |
| discount_calc      | 할인 계산기           |
| card_benefit       | 카드 제휴 혜택        |
| long_term_benefit  | 장기고객 혜택         |
| unused_benefit     | 미사용 혜택           |
| family_bundle      | 가족 결합 조회        |
| total_bundle       | 총액결합 할인         |
| bundle_apply       | 결합 가입 신청        |
| internet           | 인터넷 상품 조회      |
| iptv               | IPTV 상품 조회        |
| wifi               | 홈WiFi 조회           |
| contract_status    | 약정 상태 조회        |
| renewal_benefit    | 재약정 혜택 조회      |
| competitor_compare | 타사 혜택 비교        |
| mnp                | 번호이동 혜택 조회    |
| penalty            | 위약금 조회           |

* Behavioral Pattern Feature 정의

| **Feature**          | **계산 방법**                         | **의미**                 |
| -------------------------- | ------------------------------------------- | ------------------------------ |
| explored_entity_count_5m   | 최근 5분 내 탐색한 entity 개수              | 관심 영역 다양성               |
| comparison_action_count_5m | 최근 5분 내 comparison_action 발생 횟수     | 혜택/상품 비교 성향            |
| decision_action_count_5m   | 최근 5분 내 decision_action 발생 횟수       | 가입·변경·재약정 실행 의향   |
| churn_action_count_5m      | 최근 5분 내 churn_action 발생 횟수          | 이탈 검토 강도                 |
| action_intensity_5m        | 최근 5분 내 전체 action 수                  | 행동 활성도                    |
| dominant_entity_5m         | 최근 5분 내 가장 많이 탐색한 entity         | 현재 주요 관심 영역            |
| event_transition_pattern   | 최근 event_type 흐름                        | 행동 변화                      |
| entity_transition_pattern  | 최근 entity 흐름                            | 관심 영역 변화                 |
| last_entity                | 가장 최근 탐색한 entity                     | 현재 시점의 직접적인 관심 대상 |
| entity_focus_ratio_5m      | dominant_entity 발생 횟수 ÷ 전체 action 수 | 특정 관심사 집중도             |

* 예시 Output : Behavior Pattern Feature Table

| **window_end** | **session_id** | **cust_id** | **event_type** | **entity**   | **explored_entity_count_5m** | **comparison_action_count_5m** | **decision_action_count_5m** | **churn_action_count_5m** | **action_intensity_5m** | **dominant_entity_5m** | **event_transition_pattern** | **entity_transition_pattern** | **last_entity** | **entity_focus_ratio_5m** |
| -------------------- | -------------------- | ----------------- | -------------------- | ------------------ | ---------------------------------- | ------------------------------------ | ---------------------------------- | ------------------------------- | ----------------------------- | ---------------------------- | ---------------------------------- | ----------------------------------- | --------------------- | ------------------------------- |
| 12:05                | S001                 | A001              | comparison_action    | total_bundle       | 2                                  | 1                                    | 0                                  | 0                               | 3                             | total_bundle                 | action_select → comparison_action | family_bundle → total_bundle       | total_bundle          | 0.67                            |
| 12:05                | S002                 | A002              | action_select        | iptv               | 3                                  | 0                                    | 0                                  | 0                               | 4                             | internet                     | action_select → action_select     | internet → iptv                    | iptv                  | 0.50                            |
| 12:05                | S003                 | A003              | decision_action      | renewal_benefit    | 2                                  | 0                                    | 1                                  | 0                               | 3                             | renewal_benefit              | action_select → decision_action   | contract_status → renewal_benefit  | renewal_benefit       | 0.67                            |
| 12:05                | S004                 | A004              | churn_action         | competitor_compare | 3                                  | 1                                    | 0                                  | 2                               | 5                             | competitor_compare           | comparison_action → churn_action  | penalty → competitor_compare       | competitor_compare    | 0.60                            |

### 3.3. 실시간 Intent 추론

* Batch Feature에 Event Feature와 Behavioral Pattern Feature를 추가 결합하여 각 L3 Intent의 Intent Score 재산정
  * Rule 기반 추론은 사전 정의된 조건식을 통해 Score 도출
  * 모델 기반 추론은 Batch Feature, Event Feature, Behavioral Pattern Feature를 통합한 입력 데이터를 활용하여 Score 도출
* 이후 산정된 Intent Score를 공통 스케일로 정규화하고, 최종 Real-time Intent Top-K 생성
* 예시 Output : Customer Intent Score

| **Rank** | **L1**     | **L2**        | **L3**             | **Score** | **Probability** |
| -------------- | ---------------- | ------------------- | ------------------------ | --------------- | --------------------- |
| 1              | 유지/락인        | 재약정 검토         | 재약정 혜택 비교         | 96              | 27.4%                 |
| 2              | 할인 최적화      | 추가 혜택 탐색      | 추가 할인 가능 여부 확인 | 82              | 23.4%                 |
| 3              | 할인 최적화      | 결합 할인 확대 검토 | 총액결합 할인 확대 검토  | 74              | 21.1%                 |
| 4              | 회선/서비스 확장 | 홈서비스 확장       | IPTV 결합 추가 검토      | 60              | 17.1%                 |
| 5              | 가입 확대        | 결합 상품 탐색      | 할인 중심 결합 상품 탐색 | 38              | 10.9%                 |

1. **Base Intent 추론 결과**

| **Rank** | **L1**     | **L2**        | **L3**             | **Score** | **Probability** |
| -------------- | ---------------- | ------------------- | ------------------------ | --------------- | --------------------- |
| 1              | 할인 최적화      | 추가 혜택 탐색      | 추가 할인 가능 여부 확인 | 87              | 26.1%                 |
| 2              | 할인 최적화      | 결합 할인 확대 검토 | 총액결합 할인 확대 검토  | 81              | 24.3%                 |
| 3              | 유지/락인        | 재약정 검토         | 재약정 혜택 비교         | 68              | 20.4%                 |
| 4              | 회선/서비스 확장 | 홈서비스 확장       | IPTV 결합 추가 검토      | 52              | 15.6%                 |
| 5              | 가입 확대        | 결합 상품 탐색      | 할인 중심 결합 상품 탐색 | 45              | 13.5%                 |

2. **앱 행동(action) 발생**

* (Step 1) 약정 혜택 확인 → (Step 2) 재약정 혜택 조회, 재약정 상담 신청

3. **Event Feature 생성**

* renewal_consult_submit(재약정 상담 신청) = True

4. **Behavioral Pattern Feature 생성**

| **Feature**          | **값** | **Feature**     | **값**                     |
| -------------------------- | ------------ | --------------------- | -------------------------------- |
| explored_entity_count_5m   | 1            | churn_action_count_5m | 0                                |
| repeated_entity_count_5m   | 2            | dominant_entity_5m    | retention                        |
| comparison_action_count_5m | 1            | last_2_events         | action_select → decision_action |
| decision_action_count_5m   | 1            | last_2_entities       | retention → retention           |

5. **실시간 Intent 재추론**

| **Rank** | **L1**     | **L2**        | **L3**             | **Score** | **Probability** | **Δ Score** | **Rank Change** |
| -------------- | ---------------- | ------------------- | ------------------------ | --------------- | --------------------- | ------------------ | --------------------- |
| 1              | 유지/락인        | 재약정 검토         | 재약정 혜택 비교         | 96              | 27.4%                 | +28                | ↑2                   |
| 2              | 할인 최적화      | 추가 혜택 탐색      | 추가 할인 가능 여부 확인 | 82              | 23.4%                 | -5                 | ↓1                   |
| 3              | 할인 최적화      | 결합 할인 확대 검토 | 총액결합 할인 확대 검토  | 74              | 21.1%                 | -7                 | ↓1                   |
| 4              | 회선/서비스 확장 | 홈서비스 확장       | IPTV 결합 추가 검토      | 60              | 17.1%                 | +8                 | -                     |
| 5              | 가입 확대        | 결합 상품 탐색      | 할인 중심 결합 상품 탐색 | 38              | 10.9%                 | -7                 | -                     |

## 4. 초개인화 Context 저장 및 활용

### 4.1. 초개인화 Context Library 적재

* 대상 고객에 대해서 추론한 실시간 intent와 해당 Intent 추론에 활용된 feature 정보 등을 담은 customer context를 context library에 적재

| **필드**                 | **레벨** | **설명**                     |
| ------------------------------ | -------------- | ---------------------------------- |
| cust_id                        | Context        | 고객 ID                            |
| created_at                     | Intent         | Intent 생성 일시                   |
| expired_at                     | Intent         | Intent 만료 일시                   |
| version                        | Intent         | Intent 추론 활용 Rule / Model 버전 |
| intent_id                      | Intent         | Intent ID                          |
| intent_nm_ko                   | Intent         | Intent 한글명                      |
| L0/L1                          | Intent         | Intent 분류                        |
| score                          | Intent         | Intent Score                       |
| inference_type                 | Intent         | Rule / Model / Vector 구분         |
| evidence.rule_id               | Evidence       | Intent별 발생 원인 Rule id         |
| evidence.features.source       | Evidence       | batch / event / behavior 출처 구분 |
| evidence.features.feature      | Evidence       | Evidence Feature 명                |
| evidence.features.actual_value | Evidence       | 추론 시점의 Evidence Feature 값    |

* 예시 Output : customer context

<pre class="code-block" data-language="yaml" data-prosemirror-content-type="node" data-prosemirror-node-name="codeBlock" data-prosemirror-node-block="true"><div class="code-block--start" contenteditable="false"></div><div class="code-block-content-wrapper"><div contenteditable="false"><div class="code-block-gutter-pseudo-element" data-label="1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26"></div></div><div class="code-content"><code data-language="yaml" spellcheck="false" data-testid="code-block--code" aria-label="" data-local-id="b14a5d9b-ac55-4a60-95db-7ec829e2cc43">  {
    // 고객 Context 식별
    "cust_id":        "A001",
    "created_at":     "2026-05-27T12:05:00+09:00",
    "expired_at":     "2026-05-27T12:35:00+09:00",

    // Intent
    "intent_id":      "INT-BUNDLE-2110",
    "intent_nm_ko":   "가족 결합 가능 여부 확인",
    "version":     "1.0.0",
    "L0":             "결합",
    "L1":             "가입 확대",

    "inference_type":  "Rule",

    // Evidence
    "evidence": [
      {
        "rule_id":     "RULE-BUNDLE-1110-001",
        "features": [
          { "source": "batch", "feature": "family_line_count",       "actual_value": 3 },
          { "source": "batch", "feature": "Bundle Opportunity Index", "actual_value": 82  }
        ]
      }
    ]
}</code></div></div><div class="code-block--end" contenteditable="false"></div></pre>

### 4.2. 활용 방안

* 추론된 Intent를 활용하여 각 채널(App Push, 고객센터, Agent)에서 고객 맞춤형 서비스 제공
  * **App Push** : 고객 행동 유도 및 혜택 안내
  * **고객센터** : 상담사 지원 및 맞춤형 안내
  * **Agent** : 개인화 추천, 비교·분석 및 의사결정 지원

*Intent 분류별 대표 활용 예시

| **L1**                    | **L2**                                           | **L3**                                              | **앱 Push**                                                      | **고객센터**                                                  | **Agent**                                      |
| ------------------------------- | ------------------------------------------------------ | --------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------- |
| 가입 확대                       | 결합 가능 여부 탐색                                    | 가족 결합 가능 여부 확인                                  | 👨‍👩‍👧‍👦 가족 결합 시 추가 할인을 받을 수 있는지 확인해보세요    | 가족 결합 가능 여부와 예상 할인 금액을 안내해드릴게요               | 가족 회선을 결합하면 얼마나 할인되는지 계산해볼까요? |
| 인터넷/IPTV 결합 가능 여부 확인 | 🌐 인터넷·TV 결합 시 받을 수 있는 혜택을 확인해보세요 | 현재 이용 상품 기준 결합 가능 상품을 안내해드릴게요       | 인터넷과 TV를 함께 이용하면 어떤 혜택이 생기는지 알아볼까요?           |                                                                     |                                                      |
| 결합 상품 탐색                  | 나에게 맞는 결합 상품 탐색                             | 🎯 고객님에게 적합한 결합 상품을 추천해드립니다           | 이용 패턴에 맞는 결합 상품을 안내해드릴게요                            | 가장 유리한 결합 상품을 함께 찾아볼까요?                            |                                                      |
| 가입 혜택 탐색                  | 신규 가입 혜택 확인                                    | 🎁 신규 가입 고객 전용 혜택을 확인해보세요                | 현재 가입 가능한 할인 혜택을 안내해드릴게요                            | 가입 시 받을 수 있는 혜택을 정리해볼까요?                           |                                                      |
| 가입 실행 검토                  | 가입 절차 확인                                         | 📝 결합 가입 절차를 미리 확인해보세요                     | 가입에 필요한 절차와 준비사항을 설명드릴게요                           | 가입까지 어떤 단계가 필요한지 안내해드릴까요?                       |                                                      |
| 할인 최적화                     | 현재 혜택 점검                                         | 현재 적용 혜택 확인                                       | 📋 현재 받고 있는 결합 혜택을 확인해보세요                             | 현재 적용 중인 할인 내역을 안내해드릴게요                           | 지금 받고 있는 혜택을 한 번에 정리해볼까요?          |
| 추가 혜택 탐색                  | 혜택 적용 누락 여부 확인                               | 🔍 놓치고 있는 혜택이 있는지 확인해보세요                 | 적용 가능한 추가 혜택을 찾아드릴게요                                   | 현재 조건에서 추가로 받을 수 있는 혜택이 있는지 확인해볼까요?       |                                                      |
| 결합 할인 확대 검토             | 총액결합 할인 확대 검토                                | 📉 결합 구성을 변경하면 할인 금액이 더 커질 수 있습니다   | 현재 결합 기준 추가 할인 가능 여부를 확인해드릴게요                    | 결합 구조를 변경했을 때 할인 금액이 얼마나 늘어나는지 계산해볼까요? |                                                      |
| 혜택 활용 최적화                | OTT/콘텐츠 혜택 활용 검토                              | 🎬 사용 가능한 OTT 혜택을 확인해보세요                    | 현재 이용 가능한 콘텐츠 혜택을 안내해드릴게요                          | 아직 사용하지 않은 OTT 혜택이 있는지 확인해볼까요?                  |                                                      |
| 회선/서비스 확장                | 가족 회선 확장 및 분리                                 | 가족 회선 추가 검토                                       | 👨‍👩‍👧‍👦 가족 회선을 추가하면 더 큰 할인 혜택을 받을 수 있습니다 | 가족 회선 추가 시 예상 혜택을 안내해드릴게요                        | 가족 회선을 추가하면 얼마나 절약되는지 계산해볼까요? |
| 홈서비스 확장                   | 인터넷 결합 추가 검토                                  | 🌐 인터넷 결합 시 추가 혜택을 받을 수 있습니다            | 인터넷 결합 상품을 안내해드릴게요                                      | 인터넷을 함께 이용하면 얼마나 절약되는지 알아볼까요?                |                                                      |
| IPTV 결합 추가 검토             | 📺 IPTV 결합 고객 전용 혜택을 확인해보세요             | IPTV 추가 시 요금과 혜택을 비교해드릴게요                 | IPTV를 추가하면 어떤 혜택이 생기는지 살펴볼까요?                       |                                                                     |                                                      |
| 스마트 디바이스 확장            | 워치 회선 추가                                         | ⌚ 워치 회선을 추가하면 더욱 편리하게 이용할 수 있습니다  | 워치 전용 회선 혜택을 안내해드릴게요                                   | 스마트워치 연결 시 이용 가능한 혜택을 확인해볼까요?                 |                                                      |
| 결합 구조 재구성                | 명의 변경 기반 결합 재구성                             | 🔄 결합 구조를 변경하면 더 유리한 혜택을 받을 수 있습니다 | 명의 변경 시 가능한 결합 구성을 안내해드릴게요                         | 현재 상황에 맞게 결합을 다시 구성해볼까요?                          |                                                      |
| 유지/락인                       | 재약정 검토                                            | 재약정 혜택 비교                                          | 🎁 재약정 시 받을 수 있는 혜택을 확인해보세요                          | 현재 재약정 가능 혜택을 비교해드릴게요                              | 재약정과 현재 조건을 비교해볼까요?                   |
| 결합 유지 최적화                | 현재 결합 유지 가치 비교                               | 📊 현재 결합 유지 시 혜택을 분석해보세요                  | 현재 결합 유지와 변경 시 혜택을 비교해드릴게요                         | 지금 결합을 유지하는 것이 가장 유리한지 확인해볼까요?               |                                                      |
| 이탈 고려                       | 경쟁사 비교                                            | 타사 결합 혜택/가격 비교                                  | 🏆 현재 결합과 타사 혜택을 비교해보세요                                | 경쟁사 결합 상품과 비교해드릴게요                                   | 현재 혜택과 타사 혜택을 나란히 비교해볼까요?         |
| 혜택/비용 불만                  | 통신비 부담 증가                                       | 💰 통신비를 줄일 수 있는 방법을 확인해보세요              | 비용 부담을 줄일 수 있는 상품을 안내해드릴게요                         | 지금보다 통신비를 절약할 수 있는 방법을 찾아볼까요?                 |                                                      |
| 품질 불만                       | 인터넷 품질 불만                                       | 🚨 인터넷 품질 개선 방법을 확인해보세요                   | 현재 품질 상태를 점검해드릴게요                                        | 인터넷 이용 환경을 함께 점검해볼까요?                               |                                                      |
| 해지 검토                       | 위약금 확인                                            | 📄 해지 전 위약금 정보를 미리 확인해보세요                | 해지 시 발생 가능한 위약금을 안내해드릴게요                            | 지금 해지하면 위약금이 얼마나 발생하는지 확인해볼까요?              |                                                      |
