"""Tests for the Gemini call in narjes_custom.ai_intake.extraction.

No network: genai.Client is replaced by a fake whose replies are scripted.
"""

import json
import unittest
from types import SimpleNamespace
from unittest import mock

from narjes_custom.ai_intake import extraction as ex

GOOD = {"customer_name": "زبون تجريبي", "phone_numbers": ["07700000101"], "order_items": [], "currency": "IQD", "gift": False, "extraction_notes": []}


def reply(text, finish="STOP", prompt=900, output=120, thoughts=300, cached=0):
    usage = SimpleNamespace(prompt_token_count=prompt, candidates_token_count=output, thoughts_token_count=thoughts, cached_content_token_count=cached)
    return SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))], usage_metadata=usage)


class ApiError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


SETTINGS = {"model_name": "gemini-test", "temperature": "0.1", "max_tokens": 8192, "request_timeout": 60, "max_retries": 0, "thinking_level": ""}


class Base(unittest.TestCase):
    def run_extraction(self, replies, settings=None, conf=None):
        values = dict(SETTINGS, **(settings or {}))
        client = mock.Mock()
        client.models.generate_content.side_effect = replies
        fake_frappe = SimpleNamespace(conf=conf or {}, log_error=mock.Mock())
        with mock.patch.object(ex, "frappe", fake_frappe), \
             mock.patch.object(ex.ai_settings, "get_settings", return_value=SimpleNamespace(get=values.get)), \
             mock.patch.object(ex, "resolve_api_key", return_value="key"), \
             mock.patch.object(ex, "get_prompt_catalog", return_value=[]), \
             mock.patch.object(ex, "_build_system_prompt", return_value="PROMPT"), \
             mock.patch.object(ex.genai, "Client", return_value=client):
            try:
                result = ex.extract_order_with_meta("order text")
            finally:
                self.calls = client.models.generate_content.call_args_list
                self.log_error = fake_frappe.log_error
        return result


class TestExtraction(Base):
    def test_good_reply_with_metrics(self):
        extracted, meta = self.run_extraction([reply(json.dumps(GOOD), cached=512)])
        self.assertEqual(extracted, GOOD)
        self.assertEqual(meta["attempts"], 1)
        self.assertEqual(meta["finish_reason"], "STOP")
        self.assertEqual((meta["prompt_tokens"], meta["output_tokens"], meta["thinking_tokens"], meta["cached_tokens"]), (900, 120, 300, 512))
        self.assertEqual(meta["model"], "gemini-test")
        self.assertIsNone(self.calls[0].kwargs["config"].thinking_config)

    def test_cut_off_reply_is_retried_once_with_double_budget(self):
        cut = reply('{"customer_name": "زبون', finish="MAX_TOKENS")
        extracted, meta = self.run_extraction([cut, reply(json.dumps(GOOD))])
        self.assertEqual(extracted, GOOD)
        self.assertEqual(meta["attempts"], 2)
        self.assertEqual([c.kwargs["config"].max_output_tokens for c in self.calls], [8192, 16384])

    def test_cut_off_twice_fails_clearly(self):
        cut = reply('{"customer_name": "زبون', finish="MAX_TOKENS")
        with self.assertRaises(ex.ExtractionError) as ctx:
            self.run_extraction([cut, cut])
        self.assertIn("MAX_TOKENS", str(ctx.exception))

    def test_thinking_level_is_sent_when_set(self):
        self.run_extraction([reply(json.dumps(GOOD))], settings={"thinking_level": "low"})
        self.assertEqual(self.calls[0].kwargs["config"].thinking_config.thinking_level.lower(), "low")

    def test_rejected_thinking_level_is_dropped_once_and_logged(self):
        extracted, _meta = self.run_extraction(
            [ApiError(400, "Invalid thinking_level for this model"), reply(json.dumps(GOOD))],
            settings={"thinking_level": "minimal"},
        )
        self.assertEqual(extracted, GOOD)
        self.assertIsNone(self.calls[1].kwargs["config"].thinking_config)
        self.log_error.assert_called_once()

    def test_other_client_errors_are_not_retried_without_thinking(self):
        with self.assertRaises(ex.ExtractionError):
            self.run_extraction([ApiError(401, "bad key")], settings={"thinking_level": "low"})
        self.assertEqual(len(self.calls), 1)

    def test_stub_only_on_a_production_copy(self):
        text = "📞 رقم الهاتف: ٠٧٧٠٠٠٠٠١٠١"
        with mock.patch.object(ex, "frappe", SimpleNamespace(conf={"narjes_ai_intake_stub": 1})), \
             mock.patch.object(ex.ai_settings, "get_settings", return_value=SimpleNamespace(get=SETTINGS.get)), \
             mock.patch.object(ex, "resolve_api_key", return_value=None):
            # stub flag without the prod-copy flag: the stub must not be used
            with self.assertRaises(ex.ExtractionError):
                ex.extract_order_with_meta(text)
        with mock.patch.object(ex, "frappe", SimpleNamespace(conf={"narjes_ai_intake_stub": 1, "narjes_is_prod_copy": 1})), \
             mock.patch.object(ex.ai_settings, "get_settings", return_value=SimpleNamespace(get=SETTINGS.get)):
            extracted, meta = ex.extract_order_with_meta(text)
        self.assertEqual(meta["model"], "stub")
        self.assertEqual(extracted["order_items"], [])


class TestExtractOrder(Base):
    def test_returns_the_dict(self):
        with mock.patch.object(ex, "extract_order_with_meta", return_value=(GOOD, {})):
            self.assertEqual(ex.extract_order("x"), GOOD)


if __name__ == "__main__":
    unittest.main()
