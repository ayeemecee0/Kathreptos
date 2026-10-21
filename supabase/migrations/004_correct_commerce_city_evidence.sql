-- Repair the previously seeded Commerce City government authority citation.
-- The original source was official but on a Colorado state .co.us host;
-- our intentional policy requires independent evidence hosted on .gov.
-- CDOT's 2025 I-270 technical report cites City of Commerce City records
-- and official c3gov.com pages on a Colorado Department of Transportation .gov.
DO $correct_commerce_city_evidence$
DECLARE
  updated_rows integer;
BEGIN
  UPDATE public.official_government_domains
  SET evidence_url = 'https://www.codot.gov/projects/studies/i270study/assets/deis/section4f-techreport.pdf',
      review_notes = 'The Colorado Department of Transportation July 2025 I-270 Section 4(f) Resources Technical Report on codot.gov cites the City of Commerce City and multiple c3gov.com municipal documents; the reviewed Commerce City, Colorado jurisdiction is distinct from Commerce, California. The official city council website is the separate Legistar-link evidence.'
  WHERE domain = 'c3gov.com'
    AND legistar_tenant = 'commerce'
    AND jurisdiction_label = 'Commerce City, CO'
    AND verification_status = 'verified'
    AND evidence_url = 'https://dnrweblink.state.co.us/cwcbsearch/0/edoc/227433/CommerceCity_XericDemo_Application.pdf';
  GET DIAGNOSTICS updated_rows = ROW_COUNT;
  IF updated_rows <> 1 THEN
    RAISE EXCEPTION 'Expected to correct exactly one known Commerce City domain row; got %', updated_rows;
  END IF;
END;
$correct_commerce_city_evidence$;
