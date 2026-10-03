"""Offline tests of the extraction boundary; all elements are synthetic."""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import censys_exposure as c


class ExtractionBoundaryTests(unittest.TestCase):
    def fixture(self):
        return {"result": {"total_count": 12, "other_count": 2,
                           "is_more_than_total_hits": True,
                           "query_duration_millis": 3,
                           "buckets": [{"key": "ES", "count": 12}],
                           "unexpected_individual_record": "must not persist"}}

    def test_normalization_preserves_caveats_discards_extra_data(self):
        data = c.normalize_response(self.fixture(), "host.location.country_code")
        self.assertEqual(data["other_count"], 2)
        self.assertTrue(data["is_more_than_total_hits"])
        self.assertNotIn("unexpected_individual_record", data)

    def test_country_boundary_and_invalid_counts_rejected(self):
        response = self.fixture()
        response["result"]["buckets"][0]["key"] = "FR"
        with self.assertRaises(ValueError):
            c.normalize_response(response, "host.location.country_code")
        response = self.fixture()
        response["result"]["buckets"][0]["count"] = -1
        with self.assertRaises(ValueError):
            c.normalize_response(response, "host.location.country_code")

    def test_no_redirects(self):
        self.assertIsNone(c.NoRedirect().redirect_request(None, None, 302, None, None, "https://invalid.example"))

    def test_plan_is_aggregate_only_and_captures_coobserved_services(self):
        plan = c.make_plan()
        self.assertEqual(len(plan["jobs"]), 23)
        self.assertEqual(len({x["id"] for x in plan["jobs"]}), 23)
        for job in plan["jobs"]:
            self.assertIn(job["request"]["field"], c.FIELDS)
            self.assertEqual(job["request"]["count_by_level"], ".")
            self.assertIn(c.COUNTRY, job["request"]["query"])
        jobs = {j["id"]: j["request"] for j in plan["jobs"]}
        self.assertFalse(jobs["primary_protocols"]["filter_by_query"])
        self.assertTrue(jobs["es_ics_protocols"]["filter_by_query"])
        self.assertEqual(jobs["primary_total"], jobs["primary_total_end"])

    def test_denial_stops_after_one_request_and_does_not_leak(self):
        # Clearly synthetic credentials are confined to a temporary directory.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "SYNTHETIC_TEST_TOKEN_NOT_A_CREDENTIAL"
            credential_file = root / "credentials.txt"
            credential_file.write_text(f"CENSYS_API_TOKEN={secret}\nCENSYS_ORG_ID=SYNTHETIC_ORG\n")
            error = urllib.error.HTTPError(c.ENDPOINT, 403, secret, {}, io.BytesIO(secret.encode()))
            with patch.object(c.urllib.request, "build_opener") as build, patch("sys.stdout", new_callable=io.StringIO) as log:
                build.return_value.open.side_effect = error
                ok = c.collect(c.make_plan(), credential_file, root / "run")
                self.assertFalse(ok)
                self.assertEqual(build.return_value.open.call_count, 1)
                self.assertNotIn(secret, log.getvalue())
            run = json.loads((root / "run/aggregates.json").read_text())
            self.assertEqual(run["status"], "incomplete")
            self.assertEqual(run["results"][0]["http_status"], 403)
            self.assertNotIn("aggregate", run["results"][0])
            for path in (root / "run").iterdir():
                self.assertNotIn(secret, path.read_text())
                self.assertNotIn("SYNTHETIC_ORG", path.read_text())


if __name__ == "__main__":
    unittest.main()
