"""
Tests for SUB (Subcontractor Management) -- no test file existed for
this staff-facing module before this batch (test_scp.py covers the
separate, portal-authenticated Subcontractor Portal, not this one).
Focuses on the real list/detail endpoints this batch's own inspection
found genuinely missing, and permission gating per this batch's own
explicit instruction to test permissions carefully.
"""


def _seed_subcontractor(client, headers, name="Prime Electrical Ltd"):
    r = client.post("/v1/sub/subcontractors", headers=headers, json={"name": name, "trade_specialty": "electrical"})
    assert r.status_code == 201
    return r.get_json()["id"]


def _seed_agreement(client, headers, subcontractor_id, agreement_number="AG-001"):
    r = client.post(
        "/v1/sub/agreements",
        headers=headers,
        json={"subcontractor_id": subcontractor_id, "agreement_number": agreement_number, "value": "5000000"},
    )
    assert r.status_code == 201
    return r.get_json()["id"]


class TestSubcontractorDetail:
    def test_real_detail_endpoint_returns_the_real_subcontractor(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers, name="Chidi Electrical")

        r = client.get(f"/v1/sub/subcontractors/{sub_id}", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["name"] == "Chidi Electrical"

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        headers_a = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers_a)

        headers_b = auth_headers("b", permissions=["*"])
        r = client.get(f"/v1/sub/subcontractors/{sub_id}", headers=headers_b)
        assert r.status_code == 404


class TestAgreementDetail:
    def test_real_detail_endpoint_returns_the_real_agreement(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers)
        agreement_id = _seed_agreement(client, headers, sub_id, agreement_number="AG-XYZ")

        r = client.get(f"/v1/sub/agreements/{agreement_id}", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["agreement_number"] == "AG-XYZ"

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        headers_a = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers_a)
        agreement_id = _seed_agreement(client, headers_a, sub_id)

        headers_b = auth_headers("b", permissions=["*"])
        r = client.get(f"/v1/sub/agreements/{agreement_id}", headers=headers_b)
        assert r.status_code == 404


class TestProgressEntryList:
    def test_real_list_returns_only_the_real_entries_for_this_agreement(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers)
        agreement_1 = _seed_agreement(client, headers, sub_id, "AG-1")
        agreement_2 = _seed_agreement(client, headers, sub_id, "AG-2")
        client.post(f"/v1/sub/agreements/{agreement_1}/progress-entries", headers=headers, json={"submitted_quantity": "10"})
        client.post(f"/v1/sub/agreements/{agreement_2}/progress-entries", headers=headers, json={"submitted_quantity": "20"})

        r = client.get(f"/v1/sub/agreements/{agreement_1}/progress-entries", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["submitted_quantity"] == "10.0000"


class TestMeasurementSheetList:
    def test_real_list_scoped_to_the_real_agreement(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers)
        agreement_id = _seed_agreement(client, headers, sub_id)
        scope = client.post(f"/v1/sub/agreements/{agreement_id}/scope-items", headers=headers, json={"description": "Wiring", "is_lump_sum": True, "lump_sum_amount": "100000"})
        scope_item_id = scope.get_json()["id"]
        client.post("/v1/sub/measurement-sheets", headers=headers, json={"agreement_id": agreement_id, "scope_item_id": scope_item_id, "verified_quantity": "5"})

        r = client.get(f"/v1/sub/agreements/{agreement_id}/measurement-sheets", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1


class TestBackChargeList:
    def test_real_list_returns_the_real_charges(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers)
        agreement_id = _seed_agreement(client, headers, sub_id)
        client.post(f"/v1/sub/agreements/{agreement_id}/back-charges", headers=headers, json={"description": "Damaged material", "amount": "50000"})

        r = client.get(f"/v1/sub/agreements/{agreement_id}/back-charges", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["description"] == "Damaged material"


class TestRetentionList:
    def test_real_list_returns_the_real_retention_record(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers)
        agreement_id = _seed_agreement(client, headers, sub_id)
        client.post(f"/v1/sub/agreements/{agreement_id}/retention", headers=headers, json={"percentage": "10"})

        r = client.get(f"/v1/sub/agreements/{agreement_id}/retention", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["percentage"] == "10.00"


class TestClaimList:
    def test_real_list_returns_the_real_claim(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers)
        agreement_id = _seed_agreement(client, headers, sub_id)
        client.post(f"/v1/sub/agreements/{agreement_id}/claims", headers=headers, json={"claim_type": "delay", "description": "Late drawings"})

        r = client.get(f"/v1/sub/agreements/{agreement_id}/claims", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["description"] == "Late drawings"


class TestPerformanceRatingList:
    def test_real_list_returns_the_real_rating(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers)
        client.post(
            f"/v1/sub/subcontractors/{sub_id}/ratings",
            headers=headers,
            json={"quality_score": "8", "schedule_score": "7", "safety_score": "9", "responsiveness_score": "8"},
        )

        r = client.get(f"/v1/sub/subcontractors/{sub_id}/ratings", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1


class TestComplianceDocumentList:
    def test_real_list_returns_the_real_document(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers)
        client.post(f"/v1/sub/subcontractors/{sub_id}/compliance-documents", headers=headers, json={"doc_type": "insurance"})

        r = client.get(f"/v1/sub/subcontractors/{sub_id}/compliance-documents", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["doc_type"] == "insurance"


class TestSensitivePermissions:
    """This batch's own explicit instruction: test permissions
    carefully. SUB carries real commercial values (agreement value,
    payment certificates, claims) -- read/write/approve are tested
    the same way as WFM's own equivalent suite."""

    def test_a_caller_without_sub_read_cannot_list_agreements(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["wfm:read"])
        r = client.get("/v1/sub/agreements", headers=headers)
        assert r.status_code == 403

    def test_a_caller_without_sub_write_cannot_create_an_agreement(self, app, db, client, seed_tenants, auth_headers):
        headers_full = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers_full)

        headers_read_only = auth_headers("a", permissions=["sub:read"])
        r = client.post("/v1/sub/agreements", headers=headers_read_only, json={"subcontractor_id": sub_id, "agreement_number": "AG-X", "value": "1000"})
        assert r.status_code == 403

    def test_a_caller_without_sub_approve_cannot_issue_a_payment_certificate(self, app, db, client, seed_tenants, auth_headers):
        headers_full = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers_full)
        agreement_id = _seed_agreement(client, headers_full, sub_id)

        headers_write = auth_headers("a", permissions=["sub:read", "sub:write"])
        r = client.post(f"/v1/sub/agreements/{agreement_id}/payment-certificates", headers=headers_write, json={"certificate_number": "PC-1", "line_items": []})
        assert r.status_code == 403

    def test_a_caller_without_sub_approve_cannot_release_retention(self, app, db, client, seed_tenants, auth_headers):
        headers_full = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers_full)
        agreement_id = _seed_agreement(client, headers_full, sub_id)
        retention = client.post(f"/v1/sub/agreements/{agreement_id}/retention", headers=headers_full, json={"percentage": "5"})
        retention_id = retention.get_json()["id"]

        headers_write = auth_headers("a", permissions=["sub:read", "sub:write"])
        r = client.post(f"/v1/sub/retention/{retention_id}/release", headers=headers_write, json={"stage": "final"})
        assert r.status_code == 403

    def test_a_caller_without_sub_approve_cannot_review_a_claim(self, app, db, client, seed_tenants, auth_headers):
        headers_full = auth_headers("a", permissions=["*"])
        sub_id = _seed_subcontractor(client, headers_full)
        agreement_id = _seed_agreement(client, headers_full, sub_id)
        claim = client.post(f"/v1/sub/agreements/{agreement_id}/claims", headers=headers_full, json={"claim_type": "delay", "description": "x"})
        claim_id = claim.get_json()["id"]

        headers_write = auth_headers("a", permissions=["sub:read", "sub:write"])
        r = client.post(f"/v1/sub/claims/{claim_id}/review", headers=headers_write, json={"decision": "approved"})
        assert r.status_code == 403
