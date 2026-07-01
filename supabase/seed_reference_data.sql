-- GTF Accounting Conversion - initial reference data

insert into public.standard_accounts
  (account_key, standard_code, internal_label, ifrs_account, mapping_type, rule_summary)
values
  ('cash', 'A1000', '현금및현금성자산', 'Cash and cash equivalents', 'simple', '사용 제한 여부를 확인한 뒤 현금및현금성자산으로 단순 매핑합니다.'),
  ('receivables', 'A1100', '매출채권', 'Trade and other receivables', 'judgment', 'IFRS 9 기준에 따라 매출채권 분류와 기대신용손실 충당금을 검토합니다.'),
  ('inventory', 'A1200', '재고자산', 'Inventories', 'simple', 'IAS 2 재고자산으로 매핑하고 원가와 순실현가능가치 비교를 검토합니다.'),
  ('lease', 'A2100', '리스', 'Right-of-use asset and lease liability', 'judgment', 'IFRS 16 측정을 위해 리스기간, 지급액, 선택권, 할인율을 추가 확인합니다.'),
  ('development', 'A3100', '개발비', 'Intangible assets or R&D expense', 'judgment', 'IAS 38 개발단계 자산화 요건 충족 여부를 검토합니다.'),
  ('revenue', 'R1000', '수익', 'Revenue from contracts with customers', 'judgment', 'IFRS 15 기준에 따라 수행의무와 수익인식 시점을 확인합니다.'),
  ('financial_instrument', 'F1000', '금융상품', 'Financial assets/liabilities', 'judgment', 'IFRS 9 기준에 따라 사업모형과 계약상 현금흐름 특성을 검토합니다.'),
  ('provision', 'L2200', '충당부채', 'Provisions and contingencies', 'judgment', 'IAS 37 기준에 따라 현재의무, 유출가능성, 신뢰성 있는 추정 여부를 검토합니다.'),
  ('other', 'X9999', '미분류 계정', 'Review required', 'judgment', '자동 매핑 신뢰도가 낮아 담당자 분류 검토가 필요합니다.')
on conflict (account_key) do update set
  standard_code = excluded.standard_code,
  internal_label = excluded.internal_label,
  ifrs_account = excluded.ifrs_account,
  mapping_type = excluded.mapping_type,
  rule_summary = excluded.rule_summary,
  updated_at = now();

insert into public.kgaap_accounts (id, account_key, kgaap_name, normalized_name)
values
  ('cash_1', 'cash', '현금및현금성자산', '현금및현금성자산'),
  ('cash_2', 'cash', '현금', '현금및현금성자산'),
  ('cash_3', 'cash', '예금', '현금및현금성자산'),
  ('cash_4', 'cash', '보통예금', '현금및현금성자산'),
  ('receivables_1', 'receivables', '매출채권', '매출채권'),
  ('receivables_2', 'receivables', '외상매출금', '매출채권'),
  ('receivables_3', 'receivables', '받을어음', '매출채권'),
  ('inventory_1', 'inventory', '재고자산', '재고자산'),
  ('inventory_2', 'inventory', '상품', '재고자산'),
  ('inventory_3', 'inventory', '제품', '재고자산'),
  ('inventory_4', 'inventory', '원재료', '재고자산'),
  ('lease_1', 'lease', '리스부채', '리스'),
  ('lease_2', 'lease', '사용권자산', '리스'),
  ('lease_3', 'lease', '리스', '리스'),
  ('development_1', 'development', '개발비', '개발비'),
  ('development_2', 'development', '개발원가', '개발비'),
  ('development_3', 'development', '무형자산개발비', '개발비'),
  ('revenue_1', 'revenue', '매출', '수익'),
  ('revenue_2', 'revenue', '수익', '수익'),
  ('revenue_3', 'revenue', '제품매출', '수익'),
  ('revenue_4', 'revenue', '용역매출', '수익'),
  ('financial_instrument_1', 'financial_instrument', '전환사채', '금융상품'),
  ('financial_instrument_2', 'financial_instrument', '금융상품', '금융상품'),
  ('financial_instrument_3', 'financial_instrument', '파생상품', '금융상품'),
  ('financial_instrument_4', 'financial_instrument', '상환전환우선주', '금융상품'),
  ('provision_1', 'provision', '충당부채', '충당부채'),
  ('provision_2', 'provision', '판매보증충당부채', '충당부채'),
  ('provision_3', 'provision', '복구충당부채', '충당부채'),
  ('other_1', 'other', '미분류 계정', '미분류 계정')
on conflict (id) do update set
  account_key = excluded.account_key,
  kgaap_name = excluded.kgaap_name,
  normalized_name = excluded.normalized_name,
  active = true;

insert into public.ifrs_accounts
  (id, account_key, ifrs_name, standard_ref, recognition_summary, measurement_summary, disclosure_summary)
values
  ('cash', 'cash', 'Cash and cash equivalents', 'IAS 7', '사용 제한 여부와 현금성자산 요건을 확인합니다.', '사용 제한 여부를 확인한 뒤 현금및현금성자산으로 단순 매핑합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.'),
  ('receivables', 'receivables', 'Trade and other receivables', 'IFRS 9', '분류와 기대신용손실 충당금을 검토합니다.', 'IFRS 9 기준에 따라 매출채권 분류와 기대신용손실 충당금을 검토합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.'),
  ('inventory', 'inventory', 'Inventories', 'IAS 2', '원가와 순실현가능가치 비교를 검토합니다.', 'IAS 2 재고자산으로 매핑하고 원가와 순실현가능가치 비교를 검토합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.'),
  ('lease', 'lease', 'Right-of-use asset and lease liability', 'IFRS 16', '리스기간, 지급액, 선택권, 할인율을 확인합니다.', 'IFRS 16 측정을 위해 리스기간, 지급액, 선택권, 할인율을 추가 확인합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.'),
  ('development', 'development', 'Intangible assets or R&D expense', 'IAS 38', '개발단계 자산화 요건 충족 여부를 검토합니다.', 'IAS 38 개발단계 자산화 요건 충족 여부를 검토합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.'),
  ('revenue', 'revenue', 'Revenue from contracts with customers', 'IFRS 15', '수행의무와 수익인식 시점을 확인합니다.', 'IFRS 15 기준에 따라 수행의무와 수익인식 시점을 확인합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.'),
  ('financial_instrument', 'financial_instrument', 'Financial assets/liabilities', 'IFRS 9', '사업모형과 계약상 현금흐름 특성을 검토합니다.', 'IFRS 9 기준에 따라 사업모형과 계약상 현금흐름 특성을 검토합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.'),
  ('provision', 'provision', 'Provisions and contingencies', 'IAS 37', '현재의무, 유출가능성, 신뢰성 있는 추정을 검토합니다.', 'IAS 37 기준에 따라 현재의무, 유출가능성, 신뢰성 있는 추정 여부를 검토합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.'),
  ('other', 'other', 'Review required', 'Manual Review', '담당자 분류 검토가 필요합니다.', '자동 매핑 신뢰도가 낮아 담당자 분류 검토가 필요합니다.', '검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.')
on conflict (id) do update set
  ifrs_name = excluded.ifrs_name,
  standard_ref = excluded.standard_ref,
  recognition_summary = excluded.recognition_summary,
  measurement_summary = excluded.measurement_summary,
  disclosure_summary = excluded.disclosure_summary;

insert into public.mapping_rules
  (id, account_key, source_standard, target_standard, mapping_type, rule_summary, checklist_json)
select
  account_key || '_kgaap_ifrs',
  account_key,
  'K-GAAP',
  'IFRS',
  mapping_type,
  rule_summary,
  case account_key
    when 'lease' then '[{"key":"lease_term_months","label":"리스기간(개월)","type":"number","required":true},{"key":"monthly_payment","label":"월 리스료","type":"number","required":true},{"key":"discount_rate","label":"증분차입이자율(%)","type":"number","required":true},{"key":"renewal_option","label":"연장선택권 행사가 상당히 확실한가?","type":"boolean","required":false}]'::jsonb
    when 'development' then '[{"key":"technical_feasibility","label":"기술적 실현가능성이 입증되었는가?","type":"boolean","required":true},{"key":"intention_to_complete","label":"완성 의도와 능력이 있는가?","type":"boolean","required":true},{"key":"probable_future_benefits","label":"미래경제적효익이 개연적인가?","type":"boolean","required":true},{"key":"reliable_measurement","label":"원가를 신뢰성 있게 측정할 수 있는가?","type":"boolean","required":true}]'::jsonb
    when 'revenue' then '[{"key":"contract_type","label":"계약 유형","type":"text","required":true},{"key":"performance_obligations","label":"수행의무","type":"text","required":true},{"key":"recognition_timing","label":"한 시점 또는 기간에 걸친 인식","type":"text","required":true},{"key":"variable_consideration","label":"변동대가가 있는가?","type":"boolean","required":false}]'::jsonb
    when 'financial_instrument' then '[{"key":"instrument_terms","label":"주요 계약조건","type":"text","required":true},{"key":"business_model","label":"보유 사업모형","type":"text","required":true},{"key":"sppi_passed","label":"원금과 이자 지급만으로 구성된 현금흐름(SPPI) 요건을 충족하는가?","type":"boolean","required":true}]'::jsonb
    when 'provision' then '[{"key":"present_obligation","label":"현재의무가 존재하는가?","type":"boolean","required":true},{"key":"probable_outflow","label":"자원 유출 가능성이 높은가?","type":"boolean","required":true},{"key":"reliable_estimate","label":"금액을 신뢰성 있게 추정할 수 있는가?","type":"boolean","required":true}]'::jsonb
    when 'receivables' then '[{"key":"credit_risk_method","label":"기대신용손실 산정 방식","type":"text","required":true},{"key":"aging_available","label":"연령분석표가 있는가?","type":"boolean","required":true}]'::jsonb
    when 'other' then '[{"key":"management_memo","label":"경영진 분류 메모","type":"text","required":true}]'::jsonb
    else '[]'::jsonb
  end
from public.standard_accounts
on conflict (id) do update set
  mapping_type = excluded.mapping_type,
  rule_summary = excluded.rule_summary,
  checklist_json = excluded.checklist_json,
  updated_at = now();

delete from public.checklist_items;
insert into public.checklist_items (id, account_key, item_key, label, input_type, required, display_order)
select
  account_key || '_' || item ->> 'key',
  account_key,
  item ->> 'key',
  item ->> 'label',
  item ->> 'type',
  (item ->> 'required')::boolean,
  ordinality
from public.mapping_rules,
jsonb_array_elements(checklist_json) with ordinality as checklist(item, ordinality)
where jsonb_array_length(checklist_json) > 0;

insert into public.standards_references (id, standard_set, reference_code, title, summary)
values
  ('ias_2', 'IFRS', 'IAS 2', 'IAS 2', '기준서 원문 연결 전까지 요약 기준정보로 사용합니다.'),
  ('ias_7', 'IFRS', 'IAS 7', 'IAS 7', '기준서 원문 연결 전까지 요약 기준정보로 사용합니다.'),
  ('ias_37', 'IFRS', 'IAS 37', 'IAS 37', '기준서 원문 연결 전까지 요약 기준정보로 사용합니다.'),
  ('ias_38', 'IFRS', 'IAS 38', 'IAS 38', '기준서 원문 연결 전까지 요약 기준정보로 사용합니다.'),
  ('ifrs_9', 'IFRS', 'IFRS 9', 'IFRS 9', '기준서 원문 연결 전까지 요약 기준정보로 사용합니다.'),
  ('ifrs_15', 'IFRS', 'IFRS 15', 'IFRS 15', '기준서 원문 연결 전까지 요약 기준정보로 사용합니다.'),
  ('ifrs_16', 'IFRS', 'IFRS 16', 'IFRS 16', '기준서 원문 연결 전까지 요약 기준정보로 사용합니다.'),
  ('manual_review', 'IFRS', 'Manual Review', 'Manual Review', '기준서 원문 연결 전까지 요약 기준정보로 사용합니다.')
on conflict (id) do update set
  standard_set = excluded.standard_set,
  reference_code = excluded.reference_code,
  title = excluded.title,
  summary = excluded.summary;
