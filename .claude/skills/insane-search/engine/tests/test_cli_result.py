"""CLI content and diagnostic parity with exactly one retrieval."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine import Attempt, FetchResult
from engine import __main__ as cli
from engine.content_safety import BEGIN_UNTRUSTED_WEB_CONTENT, END_UNTRUSTED_WEB_CONTENT


class CliResultTests(unittest.TestCase):
    def test_one_retrieval_contains_content_trace_and_failure_contract(self) -> None:
        for ok in (True, False):
            with self.subTest(ok=ok):
                result = FetchResult(
                    ok=ok, content="fixture page body", final_url="https://example.com/article",
                    verdict="strong_ok" if ok else "challenge", summary="fixture summary",
                    trace=[Attempt("probe", "fixture", "https://example.com/article",
                                   "original", None, "", status=200 if ok else 403)],
                    planned_attempts=1, executed_attempts=1,
                    untried_routes=[] if ok else ["browser"],
                    must_invoke_playwright_mcp=not ok,
                )
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(cli, "fetch", return_value=result) as fetch, \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = cli.main(["https://example.com/article", "--json-content"])
                self.assertEqual(exit_code, 0 if ok else 1)
                fetch.assert_called_once()
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["executed_attempts"], 1)
                self.assertEqual(payload["trace"][0]["status"], 200 if ok else 403)
                self.assertEqual(payload["untried_routes"], [] if ok else ["browser"])
                self.assertEqual(payload["must_invoke_playwright_mcp"], not ok)
                self.assertEqual(payload["content_length"], len("fixture page body"))
                self.assertIn("fixture page body", payload["untrusted_text"])
                self.assertLess(payload["untrusted_text"].index(BEGIN_UNTRUSTED_WEB_CONTENT),
                                payload["untrusted_text"].index("fixture page body"))
                self.assertGreater(payload["untrusted_text"].index(END_UNTRUSTED_WEB_CONTENT),
                                   payload["untrusted_text"].index("fixture page body"))

    def test_legacy_json_still_omits_content(self) -> None:
        result = FetchResult(ok=True, content="fixture page body")
        stdout = io.StringIO()
        with patch.object(cli, "fetch", return_value=result) as fetch, \
                redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            exit_code = cli.main(["https://example.com/", "--json"])
        self.assertEqual(exit_code, 0)
        fetch.assert_called_once()
        payload = json.loads(stdout.getvalue())
        self.assertNotIn("untrusted_text", payload)
        self.assertNotIn("content", payload)
        self.assertEqual(payload["content_length"], len("fixture page body"))

    def test_combined_result_masks_sensitive_final_url(self) -> None:
        result = FetchResult(
            ok=True, content="fixture body",
            final_url="https://example.com/?api_key=FIXTURE_SECRET&page=2",
            trace=[Attempt(
                "probe", "fixture", "https://example.com/?token=TRACE_SECRET", "original", None,
                "https://example.com/?session=REFERER_SECRET", status=200,
            )],
        )
        stdout = io.StringIO()
        with patch.object(cli, "fetch", return_value=result), \
                redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["https://example.com/", "--json-content"]), 0)
        payload = json.loads(stdout.getvalue())
        self.assertNotIn("FIXTURE_SECRET", payload["final_url"])
        self.assertIn("page=2", payload["final_url"])
        self.assertNotIn("FIXTURE_SECRET", payload["untrusted_text"])
        self.assertNotIn("TRACE_SECRET", payload["trace"][0]["url"])
        self.assertNotIn("REFERER_SECRET", payload["trace"][0]["referer"])


if __name__ == "__main__":
    unittest.main()
