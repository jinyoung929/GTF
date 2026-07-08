-- 표준 재무제표 양식 라인 기준 테이블 — 단일 출처(single source of truth).
-- 금감원 전자공시 재무제표 양식 구조(유동자산 → 비유동자산 → 부채 → 자본 → 손익)를 따르며,
-- 각 계정(account_key)은 이 라인 중 하나에 매핑되고 라인 순서가 곧 표시 순서가 됩니다.
-- 서버 시작 시 SQLite/Postgres 양쪽에서 그대로 실행되어 upsert됩니다 (server.py ensure_statement_templates).
-- display_order는 계정코드에서 도출한 값입니다: SECTION_ORDER(A=1, F=2, L=3, E=4, R=5, X=9) * 100000 + 코드 숫자부.
INSERT INTO financial_statement_templates
  (id, standard_set, statement_type, section, line_item, account_key, display_order, basis)
VALUES
  ('ifrs_bs_cash', 'IFRS', '재무상태표', '유동자산', '현금및현금성자산', 'cash', 101000, 'K-IFRS 제1007호 표시 목적의 현금및현금성자산 라인입니다.'),
  ('ifrs_bs_receivables', 'IFRS', '재무상태표', '유동자산', '매출채권 및 기타채권', 'receivables', 101100, 'K-IFRS 제1109호 기대신용손실 검토 후 채권 라인에 표시합니다.'),
  ('ifrs_bs_inventory', 'IFRS', '재무상태표', '유동자산', '재고자산', 'inventory', 101200, 'K-IFRS 제1002호에 따라 원가와 순실현가능가치를 검토한 뒤 표시합니다.'),
  ('ifrs_bs_prepaid_expense', 'IFRS', '재무상태표', '유동자산', '선급비용', 'prepaid_expense', 101300, '선급비용을 유동자산 선급비용 라인에 표시합니다.'),
  ('ifrs_bs_deposits', 'IFRS', '재무상태표', '비유동자산', '장기보증금(금융자산)', 'deposits', 101400, '반환 예정 보증금을 금융자산 성격의 예치금 라인에 표시합니다.'),
  ('ifrs_bs_ppe', 'IFRS', '재무상태표', '비유동자산', '유형자산', 'ppe', 101500, 'K-IFRS 제1016호 유형자산 라인에 표시하고 감가상각과 손상을 검토합니다.'),
  ('ifrs_bs_deferred_tax_asset', 'IFRS', '재무상태표', '비유동자산', '이연법인세자산', 'deferred_tax_asset', 101600, 'K-IFRS 제1012호 일시적차이 총액법으로 이연법인세자산을 인식하고 회수가능성을 검토합니다.'),
  ('ifrs_bs_investment_property', 'IFRS', '재무상태표', '비유동자산', '투자부동산', 'investment_property', 101700, 'K-IFRS 제1040호 원가모형/공정가치모형 중 선택해 투자부동산 라인에 표시합니다.'),
  ('ifrs_bs_lease_asset', 'IFRS', '재무상태표', '비유동자산/부채', '사용권자산 및 리스부채', 'lease', 102100, 'K-IFRS 제1116호에 따라 사용권자산과 리스부채 표시를 검토합니다.'),
  ('ifrs_bs_development', 'IFRS', '재무상태표 또는 손익계산서', '무형자산/비용', '무형자산 또는 연구개발비', 'development', 103100, 'K-IFRS 제1038호 개발단계 자산화 요건에 따라 표시 라인이 달라집니다.'),
  ('ifrs_bs_financial_instrument', 'IFRS', '재무상태표', '금융자산/금융부채', '금융자산 또는 금융부채', 'financial_instrument', 201000, 'K-IFRS 제1109호 분류 결과에 따라 금융자산 또는 금융부채로 표시합니다.'),
  ('ifrs_bs_trade_payables', 'IFRS', '재무상태표', '유동부채', '매입채무및기타채무', 'trade_payables', 301000, '매입채무와 기타채무를 유동부채 라인에 표시합니다.'),
  ('ifrs_bs_other_payables', 'IFRS', '재무상태표', '유동부채', '기타채무 및 미지급비용', 'other_payables', 301100, '미지급금과 미지급비용을 기타채무 라인에 표시합니다.'),
  ('ifrs_bs_current_tax_liability', 'IFRS', '재무상태표', '유동부채', '당기법인세부채', 'current_tax_liability', 301200, 'K-IFRS 제1012호 당기법인세부채 라인에 표시합니다.'),
  ('ifrs_bs_deferred_tax_liability', 'IFRS', '재무상태표', '비유동부채', '이연법인세부채', 'deferred_tax_liability', 302100, 'K-IFRS 제1012호 이연법인세부채 라인에 표시합니다.'),
  ('ifrs_bs_provision', 'IFRS', '재무상태표', '부채', '충당부채', 'provision', 302200, 'K-IFRS 제1037호 인식요건을 충족하면 충당부채로 표시하고 유동성 분류를 검토합니다.'),
  ('ifrs_bs_retirement_benefit', 'IFRS', '재무상태표', '비유동부채', '순확정급여부채', 'retirement_benefit', 302300, 'K-IFRS 제1019호 확정급여채무에서 사외적립자산을 차감한 순확정급여부채로 표시합니다.'),
  ('ifrs_bs_government_grant', 'IFRS', '재무상태표', '비유동부채', '이연정부보조금수익', 'government_grant', 302400, 'K-IFRS 제1020호 이연수익법 선택 시 이연정부보조금수익 라인에 표시합니다.'),
  ('ifrs_bs_share_capital', 'IFRS', '재무상태표', '자본', '자본금', 'share_capital', 401000, '자본금을 자본 항목에 표시합니다.'),
  ('ifrs_bs_capital_surplus', 'IFRS', '재무상태표', '자본', '자본잉여금', 'capital_surplus', 401100, '주식발행초과금 등 자본잉여금을 자본 항목에 표시합니다.'),
  ('ifrs_bs_retained_earnings', 'IFRS', '재무상태표', '자본', '이익잉여금', 'retained_earnings', 401200, '이익잉여금(결손금)을 자본 항목에 표시합니다.'),
  ('ifrs_pl_revenue', 'IFRS', '손익계산서', '수익', '고객과의 계약에서 생기는 수익', 'revenue', 501000, 'K-IFRS 제1115호 수행의무와 인식시점 검토 후 수익 라인에 표시합니다.'),
  ('ifrs_pl_cost_of_sales', 'IFRS', '손익계산서', '비용', '매출원가', 'cost_of_sales', 502000, '매출원가를 손익계산서 비용 라인에 표시합니다.'),
  ('ifrs_pl_operating_expense', 'IFRS', '손익계산서', '비용', '판매비와관리비', 'operating_expense', 503000, '판매비와관리비를 손익계산서 비용 라인에 표시합니다.'),
  ('ifrs_pl_borrowing_cost', 'IFRS', '손익계산서', '금융원가', '금융원가(차입원가 자본화 조정)', 'borrowing_cost', 504000, 'K-IFRS 제1023호 적격자산 차입원가 자본화액을 금융원가에서 차감 조정합니다.'),
  ('ifrs_review_required', 'IFRS', '검토 필요', '미분류', '검토자 분류 필요', 'other', 909999, '내부 표준계정 매핑 신뢰도가 낮아 사람이 표시 라인을 확정합니다.')
ON CONFLICT (id) DO UPDATE SET
  standard_set = excluded.standard_set,
  statement_type = excluded.statement_type,
  section = excluded.section,
  line_item = excluded.line_item,
  account_key = excluded.account_key,
  display_order = excluded.display_order,
  basis = excluded.basis,
  active = true;
