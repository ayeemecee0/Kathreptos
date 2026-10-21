"""Conservative contract-document evidence extraction and source restrictions."""
import hashlib
import unittest
from unittest.mock import patch

import auto_verify_contract_documents as contracts

TENANT = "oakland"
URL = "https://oakland.legistar.com/View.ashx?M=F&ID=123456"
PDF_ID = "955cbde1-4b0b-4cf5-89bb-3bc18de1c785"
OAKLAND_PDF = "https://oakland.legistar1.com/oakland/attachments/" + PDF_ID + ".pdf"
COMMERCE_PDF = "https://legistar.granicus.com/Commerce/attachments/" + PDF_ID + ".pdf"
MOUNTAIN_PDF = "https://legistar1.granicus.com/mountainview/attachments/" + PDF_ID + ".pdf"
PDF_TEXT = ("THIS AGREEMENT IS ENTERED INTO BY AND BETWEEN Flock Safety and "
            "the City of Oakland. Term and Termination. IN WITNESS WHEREOF "
            "the parties enter into this services agreement. ")


class FakePage:
    def __init__(self, text):
        self.value = text
    def extract_text(self):
        return self.value


class FakeReader:
    def __init__(self, text=PDF_TEXT, encrypted=False):
        self.is_encrypted = encrypted
        self.pages = [FakePage(text)]


class ContractTests(unittest.TestCase):
    def test_only_exact_government_tenant_https(self):
        self.assertEqual(contracts.official_attachment_url(URL,TENANT), URL)
        for url in (
            "http://oakland.legistar.com/View.ashx?M=F&ID=123456",
            "https://not-oakland.legistar.com/View.ashx?M=F&ID=123456",
            "https://oakland.legistar.com.evil.org/View.ashx?M=F&ID=123456",
            "https://oakland.legistar.com@evil.org/View.ashx?M=F",
            "https://127.0.0.1/internal.pdf", "file:///etc/passwd",
            "https://oakland.legistar.com/LegislationDetail.aspx?ID=7",
            "https://oakland.legistar.com/View.ashx",
            "https://oakland.legistar.com:8443/View.ashx?M=F",
        ):
            with self.subTest(url=url):
                self.assertIsNone(contracts.official_attachment_url(url,TENANT))


    def test_actual_government_api_document_url_forms(self):
        self.assertEqual(contracts.official_attachment_url(OAKLAND_PDF,"oakland"), OAKLAND_PDF)
        self.assertEqual(contracts.official_attachment_url(COMMERCE_PDF,"commerce"), COMMERCE_PDF)
        self.assertEqual(contracts.official_attachment_url(MOUNTAIN_PDF,"mountainview"), MOUNTAIN_PDF)

    def test_other_tenants_cannot_be_claimed_as_their_documents(self):
        for url in (
            "https://oakland.legistar1.com/costamesa/attachments/" + PDF_ID + ".pdf",
            "https://legistar.granicus.com/commerce/attachments/" + PDF_ID + ".pdf",
            "https://evil.granicus.com/oakland/attachments/" + PDF_ID + ".pdf",
            "https://oakland.legistar1.com/oakland/attachments/not-a-uuid.pdf",
            "https://oakland.legistar1.com/oakland/attachments/" + PDF_ID + ".pdf?token=x",
            "https://legistar.granicus.com/oakland/attachments/" + PDF_ID + ".pdf#abc",
            "https://legistar.granicus.com@evil.example/oakland/attachments/" + PDF_ID + ".pdf",
        ):
            with self.subTest(url=url):
                self.assertIsNone(contracts.official_attachment_url(url,"oakland"))

    def test_municipal_hosts_require_preapproved_exact_binding(self):
        url = "https://www.c3gov.com/meetings/city/FlockAgreement.pdf"
        self.assertIsNone(contracts.official_attachment_url(url,"commerce"))
        self.assertEqual(contracts.official_attachment_url(url,"commerce",{"www.c3gov.com"}),url)
        for bad in (
            "http://www.c3gov.com/meetings/city/FlockAgreement.pdf",
            "https://www.c3gov.com.evil.example/FlockAgreement.pdf",
            "https://www.c3gov.com/secret/../FlockAgreement.pdf",
            "https://www.c3gov.com/meetings/FlockAgreement.pdf?secret=xyz",
        ):
            with self.subTest(bad=bad):
                self.assertIsNone(contracts.official_attachment_url(bad,"commerce",{"www.c3gov.com"}))

    def test_domain_registry_requires_matching_owner_review(self):
        with patch.object(contracts,"api_request",return_value=[
            {"domain":"c3gov.com","jurisdiction_label":"Commerce City, CO",
             "legistar_tenant":"commerce","allow_www":True},
            {"domain":"other.gov","jurisdiction_label":"Not Commerce",
             "legistar_tenant":"commerce","allow_www":False},
        ]):
            result=contracts.verified_document_domains({
                "commerce":{"jurisdiction_label":"Commerce City, CO"}})
        self.assertEqual(result,{"commerce":{"c3gov.com","www.c3gov.com"}})

    def test_redirect_refuses_cross_tenant_and_untrusted_cdn(self):
        redirect=contracts.SameGovernmentHostRedirect("oakland")
        with self.assertRaises(ValueError):
            redirect.redirect_request(None,None,302,"",{},
                "https://legistar.granicus.com/commerce/attachments/" + PDF_ID + ".pdf")

    def test_attachment_requires_exact_ids_and_public_visibility(self):
        valid = {"MatterAttachmentId": 23, "MatterAttachmentMatterId": 4,
                 "MatterAttachmentHyperlink": URL, "MatterAttachmentName": "Flock Agreement"}
        self.assertEqual(contracts.attachment_metadata(valid,TENANT,4),
                         (23,"Flock Agreement",URL))
        for change in (
            {"MatterAttachmentId": "23"},
            {"MatterAttachmentMatterId": 8},
            {"MatterAttachmentShowOnInternetPage": False},
            {"MatterAttachmentHyperlink": "https://example.org/contract.pdf"},
        ):
            self.assertIsNone(contracts.attachment_metadata({**valid,**change},TENANT,4))

    def inspect(self,text=PDF_TEXT):
        with patch.object(contracts,"PdfReader",return_value=FakeReader(text)):
            return contracts.contract_pdf_evidence(b"%PDF-" + b"x"*280,"Oakland, CA")

    def test_verified_agreement_text_is_only_a_document_fact(self):
        info,issue=self.inspect()
        self.assertIsNone(issue)
        self.assertEqual(info["pdf_pages"],1)
        self.assertEqual(info["pdf_sha256"],hashlib.sha256(b"%PDF-" + b"x"*280).hexdigest())
        self.assertNotIn("signed_on",info)
        self.assertNotIn("executed",info)

    def test_hold_a_template_without_local_party(self):
        _,issue=self.inspect(PDF_TEXT.replace("Oakland","Elsewhere"))
        self.assertIn("contracting party",issue)

    def test_hold_presentation_or_false_vendor(self):
        for text in (
            "City of Oakland presentation on Flock Safety license plate readers",
            PDF_TEXT.replace("Flock Safety","Some Other Vendor"),
            "Flock Safety agenda slides for City of Oakland agreement proposal",
        ):
            with self.subTest(text=text[:50]):
                _,issue=self.inspect(text)
                self.assertIsNotNone(issue)

    def test_encrypted_pdf_and_page_limit_fail_closed(self):
        with patch.object(contracts,"PdfReader",return_value=FakeReader(encrypted=True)):
            _,issue=contracts.contract_pdf_evidence(b"%PDF-" + b"a"*250,"Oakland, CA")
            self.assertIn("encrypted",issue)
        reader=FakeReader()
        reader.pages=[FakePage(PDF_TEXT)]*61
        with patch.object(contracts,"PdfReader",return_value=reader):
            _,issue=contracts.contract_pdf_evidence(b"%PDF-" + b"a"*250,"Oakland, CA")
            self.assertIn("page limit",issue)

    def test_fingerprint_change_only_revokes_never_replaces(self):
        with patch.object(contracts,"api_request",return_value=[{"status":"revoked"}]) as request:
            self.assertTrue(contracts.revoke_changed_document(
                {"tenant":TENANT,"matter_id":4,"attachment_id":23}))
        self.assertEqual(request.call_args.kwargs["method"],"PATCH")
        self.assertEqual(request.call_args.kwargs["payload"],{"status":"revoked"})

    def test_duplicate_insert_never_rewrites_existing_document(self):
        with patch.object(contracts,"api_request",return_value=[]) as request:
            self.assertFalse(contracts.publish_document({"tenant":TENANT,"matter_id":4}))
        self.assertIn("ignore-duplicates",request.call_args.kwargs["prefer"])

    def test_dry_run_cannot_write(self):
        row={"tenant":TENANT,"matter_id":4,"official_api_url":"https://webapi.legistar.com/v1/oakland/matters/4"}
        parent={"tenant":TENANT,"matter_id":4,"status":"verified","jurisdiction_label":"Oakland, CA",
                "matter_title":"Flock Safety Agreement","file_number":"F-100"}
        reg={TENANT:{"jurisdiction_label":"Oakland, CA"}}
        doc={"MatterAttachmentId":23,"MatterAttachmentMatterId":4,
             "MatterAttachmentName":"Government agreement",
             "MatterAttachmentHyperlink":URL}
        with (patch.object(contracts,"registry_clients",return_value={TENANT:"Oakland, CA"}),
              patch.object(contracts,"verified_registry_rows",return_value=reg),
              patch.object(contracts,"fetch_public_mentions",return_value={(TENANT,4):parent}),
              patch.object(contracts,"staged_candidates",return_value=[row]),
              patch.object(contracts,"verified_document_domains",return_value={}),
              patch.object(contracts,"official_mention",return_value=(parent,None)),
              patch.object(contracts,"get_json",return_value=[doc]),
              patch.object(contracts,"fetch_document",return_value=b"%PDF-" + b"x"*280),
              patch.object(contracts,"contract_pdf_evidence",
                           return_value=({"pdf_sha256":"a"*64,"pdf_pages":1,"pdf_bytes":285},None)),
              patch.object(contracts,"api_request") as api):
            result=contracts.run(dry_run=True)
        self.assertEqual(result["qualified"],1)
        self.assertEqual(result["published"],0)
        api.assert_not_called()


if __name__=="__main__":
    unittest.main()
