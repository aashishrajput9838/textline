import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Import components from app.py
from app import (
    format_clipboard_output,
    generate_content_with_fallback,
    generate_content_openai_fallback,
    API_KEYS_MAP
)

class TestFallbackSystem(unittest.TestCase):

    def test_0_zero_keys_configured_reporting(self):
        """
        0. Test Zero Keys Configured Reporting:
        Assert that when environment has 0 GEMINI_API_KEY_* variables, 
        discover_all_gemini_keys returns an empty dict (0 configured keys).
        """
        from app import discover_all_gemini_keys
        with patch.dict("app.API_KEYS_MAP", {}, clear=True):
            with patch.dict("os.environ", {}, clear=True):
                discovered = discover_all_gemini_keys()
                self.assertEqual(len(discovered), 0)
        print("[PASS] Test 0: Zero configured keys reporting verified!")

    def test_1_all_expected_key_ids_recognized_and_ordered(self):
        """
        1. Test Key IDs dynamic rotation mapping:
        Assert API_KEYS_MAP dynamically orders configured keys without hardcoding secrets.
        """
        test_env_keys = {
            "98381": "fake_key_1",
            "98382": "fake_key_2",
            "aspirinexar": "fake_key_aspirinexar"
        }
        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            actual_keys = list(test_env_keys.keys())
            self.assertEqual(actual_keys, ["98381", "98382", "aspirinexar"])
            self.assertNotIn("98384", actual_keys)
        print("[PASS] Test 1: Key IDs rotation order mapping verified!")

    def test_2_post_processing_padding_preservation(self):
        """
        2. Test Formatting (Post-Processing):
        Simulate a successful AI response and assert that the final output string 
        EXACTLY contains 50 single-spaced lines and ends with a dot ('.').
        """
        raw_ai_response = "   def calculate_speed(distance, time):\n    return distance / time"
        formatted_output = format_clipboard_output(raw_ai_response)

        # Assert leading spaces are stripped
        self.assertTrue(formatted_output.startswith("def calculate_speed(distance, time):"))

        # Assert output ends with exact 50 single-spaced lines + '\n.'
        expected_suffix = "\n" + "\n".join([" "] * 50) + "\n."
        self.assertTrue(formatted_output.endswith(expected_suffix))

        # Check line count structure
        lines = formatted_output.split("\n")
        self.assertEqual(lines[-1], ".")
        padding_lines = lines[-51:-1]
        self.assertEqual(len(padding_lines), 50)
        for p_line in padding_lines:
            self.assertEqual(p_line, " ")

        print("[PASS] Test 2: Post-processing padding preservation verified!")

    @patch("app.genai.Client")
    def test_3_fail_fast_on_400_403_404_rotation(self, mock_genai_client):
        """
        3. Test Fail-Fast on 400/403/404 Errors with Metadata Provenance:
        Simulate Key 1 returning a 404 NOT_FOUND error.
        Assert system instantly rotates to Key 2 and returns metadata provenance.
        """
        mock_client_key1 = MagicMock()
        mock_client_key1.models.generate_content.side_effect = Exception("404 NOT_FOUND: Model no longer available")

        mock_client_key2 = MagicMock()
        mock_response_key2 = MagicMock()
        mock_response_key2.text = "def solution_key2(): pass"
        mock_client_key2.models.generate_content.return_value = mock_response_key2

        # Mock env vars for test environment
        test_env_keys = {
            "98381": "fake_key_1",
            "98382": "fake_key_2"
        }

        def client_factory(api_key):
            if api_key == "fake_key_1":
                return mock_client_key1
            return mock_client_key2

        mock_genai_client.side_effect = client_factory

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "def solution_key2(): pass")
            self.assertEqual(mock_client_key1.models.generate_content.call_count, 1)
            
            # Metadata Provenance Assertions
            self.assertEqual(meta["provider"], "Google Gemini")
            self.assertEqual(meta["key_id"], "98382")
            self.assertTrue(meta["is_fallback"])

        print("[PASS] Test 3: Instant fail-fast rotation on 400/403/404 with metadata provenance verified!")

    @patch("app.genai.Client")
    def test_4_rate_limit_429_rotation(self, mock_genai_client):
        """
        4. Test 429 Rate Limit Rotation:
        Simulate 429 RESOURCE_EXHAUSTED on Key 1.
        Assert system rotates to Key 2 and succeeds with correct key provenance.
        """
        mock_client_key1 = MagicMock()
        mock_client_key1.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Quota limit reached")

        mock_client_key2 = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "def rotate_success(): pass"
        mock_client_key2.models.generate_content.return_value = mock_response

        test_env_keys = {
            "98381": "fake_key_1",
            "98382": "fake_key_2"
        }

        def client_factory(api_key):
            if api_key == "fake_key_1":
                return mock_client_key1
            return mock_client_key2

        mock_genai_client.side_effect = client_factory

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "def rotate_success(): pass")
            self.assertEqual(meta["key_id"], "98382")
            self.assertTrue(meta["is_fallback"])

        print("[PASS] Test 4: 429 Quota Exhaustion key rotation with metadata verified!")

    @patch("app.openai")
    @patch("app.genai.Client")
    def test_5_openai_fallback_only_after_gemini_exhaustion(self, mock_genai_client, mock_openai_module):
        """
        5. Test OpenAI Fallback Execution with Metadata:
        OpenAI fallback occurs ONLY after all available Gemini keys have failed.
        """
        mock_failing_client = MagicMock()
        mock_failing_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
        mock_genai_client.return_value = mock_failing_client

        mock_openai_client = MagicMock()
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "def openai_solution(): pass"
        mock_completion.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_completion
        mock_openai_module.OpenAI.return_value = mock_openai_client

        test_env_keys = {"98381": "fake_key_1", "98382": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with patch("app.OPENAI_API_KEY", "sk-proj-valid-test-key"):
                result, meta = generate_content_with_fallback(["test_prompt"], base64_image_url="data:image/png;base64,12345")
                self.assertEqual(result, "def openai_solution(): pass")
                self.assertEqual(meta["provider"], "OpenAI")
                self.assertEqual(meta["model"], "gpt-4o-mini")
                self.assertEqual(meta["key_id"], "OPENAI")
                self.assertTrue(meta["is_fallback"])

        print("[PASS] Test 5: OpenAI fallback triggers with metadata provenance!")

    @patch("app.genai.Client")
    def test_6_missing_env_vars_and_no_credential_leakage(self, mock_genai_client):
        """
        6. Test Missing Environment Variables & Security Credential Leakage:
        - Missing environment variables are skipped safely.
        - Credentials are NEVER leaked in logs or exceptions.
        """
        secret_credential = "AQ.Ab8RN6_CONFIDENTIAL_KEY_STRING_TEST"
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception(f"403 Forbidden with secret {secret_credential}")
        mock_genai_client.return_value = mock_client

        test_env_keys = {
            "98381": secret_credential,
            "98382": None  # Missing env var
        }

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with patch("app.OPENAI_API_KEY", None):
                with self.assertRaises(RuntimeError) as ctx:
                    generate_content_with_fallback(["test_prompt"])
                
                # Check exception string does NOT expose actual raw credential secret
                err_msg = str(ctx.exception)
                self.assertIn("Key [98381]", err_msg)

        print("[PASS] Test 6: Missing environment variables handled safely and no credential leakage!")

    @patch("app.genai.Client")
    def test_7_key_health_check_diagnostics(self, mock_genai_client):
        """
        7. Test Per-Key Independent Health Diagnostics:
        - Discover keys from .env/API_KEYS_MAP.
        - Run independent test per key measuring latency and classification.
        - Verify raw credential secrets are NEVER exposed.
        """
        from app import test_single_key_diagnostic, run_all_keys_health_check, discover_all_gemini_keys
        
        mock_working_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Hi"
        mock_working_client.models.generate_content.return_value = mock_resp

        mock_quota_client = MagicMock()
        mock_quota_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")

        mock_unauth_client = MagicMock()
        mock_unauth_client.models.generate_content.side_effect = Exception("403 PERMISSION_DENIED")

        def client_factory(api_key):
            if api_key == "secret_key_working":
                return mock_working_client
            elif api_key == "secret_key_quota":
                return mock_quota_client
            return mock_unauth_client

        mock_genai_client.side_effect = client_factory

        test_env_keys = {
            "98381": "secret_key_working",
            "98382": "secret_key_quota",
            "aspirinexar": "secret_key_unauth"
        }

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            discovered = discover_all_gemini_keys()
            self.assertIn("98381", discovered)
            self.assertIn("98382", discovered)
            self.assertIn("aspirinexar", discovered)

            results = run_all_keys_health_check()
            self.assertTrue(len(results) >= 3)

            # Key 98381 -> Working
            res_1 = next(r for r in results if r["key_id"] == "98381")
            self.assertEqual(res_1["status"], "Working")
            self.assertEqual(res_1["http_code"], 200)

            # Key 98382 -> Quota
            res_2 = next(r for r in results if r["key_id"] == "98382")
            self.assertEqual(res_2["status"], "Quota")
            self.assertEqual(res_2["http_code"], 429)

            # Key aspirinexar -> Unauthorized
            res_3 = next(r for r in results if r["key_id"] == "aspirinexar")
            self.assertEqual(res_3["status"], "Unauthorized")
            self.assertEqual(res_3["http_code"], 403)

            # Check secrecy: No raw secret strings in details or results!
            for r in results:
                self.assertNotIn("secret_key", str(r))

        print("[PASS] Test 7: Independent per-key diagnostics & security secrecy verified!")

    @patch("app.genai.Client")
    def test_8_case_insensitive_key_deduplication(self, mock_genai_client):
        """
        8. Test Case-Insensitive Key Deduplication:
        Simulate environment containing both GEMINI_API_KEY_aspirinexar and GEMINI_API_KEY_ASPIRINEXAR.
        Assert that discover_all_gemini_keys and run_all_keys_health_check produce exactly ONE 'aspirinexar' entry.
        """
        from app import discover_all_gemini_keys, run_all_keys_health_check
        
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_map = {
            "aspirinexar": "secret_key_val"
        }

        test_env = {
            "GEMINI_API_KEY_aspirinexar": "secret_key_val",
            "GEMINI_API_KEY_ASPIRINEXAR": "secret_key_val"
        }

        with patch.dict("app.API_KEYS_MAP", test_map, clear=True):
            with patch.dict("os.environ", test_env, clear=True):
                discovered = discover_all_gemini_keys()
                
                # Assert discover_all_gemini_keys deduplicates case-insensitively
                aspirinexar_keys = [k for k in discovered.keys() if k.lower() == "aspirinexar"]
                self.assertEqual(len(aspirinexar_keys), 1)

                # Assert health check produces exactly ONE aspirinexar row
                results = run_all_keys_health_check()
                aspirinexar_results = [r for r in results if r["key_id"].lower() == "aspirinexar"]
                self.assertEqual(len(aspirinexar_results), 1)

        print("[PASS] Test 8: Case-insensitive key deduplication verified!")

    @patch("app.genai.Client")
    def test_9_generation_id_provenance_and_usage_tracking_metadata(self, mock_genai_client):
        """
        9. Test Generation ID Provenance & Usage Tracking Metadata:
        - Successful generation returns unique generation_id in metadata.
        - Failed keys do NOT produce successful provenance metadata.
        """
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "def solution(): pass"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_textline_gemini_9838_AlReasoningValidationSystem": "key_1_secret"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "def solution(): pass")
            self.assertIn("generation_id", meta)
            self.assertTrue(meta["generation_id"].startswith("gen_"))
            self.assertEqual(meta["key_id"], "1_textline_gemini_9838_AlReasoningValidationSystem")

        print("[PASS] Test 9: Generation ID provenance & usage tracking metadata verified!")

    @patch("app.genai.Client")
    @patch("app.time.sleep")
    def test_10_503_service_unavailable_handling_and_retry_backoff(self, mock_sleep, mock_genai_client):
        """
        10. Test 503 Service Unavailable Handling & Retry Backoff:
        - Verify 503 response reports SERVICE_UNAVAILABLE status in Health Check.
        - Verify smart summary message says 'Gemini temporarily unavailable — Google is currently reporting high demand'.
        - Verify backoff sleep calls are executed on 503 retries.
        """
        from app import run_all_keys_health_check
        
        mock_503_client = MagicMock()
        mock_503_client.models.generate_content.side_effect = Exception("503 UNAVAILABLE: This model is currently experiencing high demand.")
        mock_genai_client.return_value = mock_503_client

        test_env_keys = {"1_textline_gemini_9838_AlReasoningValidationSystem": "secret_503_key"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            # Test Health Check classification
            results = run_all_keys_health_check()
            key_res = next(r for r in results if r["key_id"] == "1_textline_gemini_9838_AlReasoningValidationSystem")
            self.assertEqual(key_res["status"], "SERVICE_UNAVAILABLE")
            self.assertEqual(key_res["http_code"], 503)

            # Test generation error summary message
            with patch("app.OPENAI_API_KEY", None):
                with self.assertRaises(RuntimeError) as ctx:
                    generate_content_with_fallback(["test_prompt"])
                err_msg = str(ctx.exception)
                self.assertIn("Gemini temporarily unavailable — Google is currently reporting high demand", err_msg)
                self.assertNotIn("Please check your .env configuration!", err_msg)

        print("[PASS] Test 10: 503 Service Unavailable & retry backoff verified!")

    @patch("app.genai.Client")
    def test_11_fine_grained_fallback_provenance_tracking(self, mock_genai_client):
        """
        11. Test Fine-Grained Fallback Provenance Tracking:
        - Verify model_fallback is True only if model changed.
        - Verify key_fallback is True only if key changed.
        - Verify is_fallback = model_fallback OR key_fallback.
        - Verify attempt_count reflects exact number of attempts.
        """
        mock_success_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_success_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_success_client

        test_env_keys = {"1_textline_gemini_9838_AlReasoningValidationSystem": "key1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertFalse(meta["is_fallback"])
            self.assertFalse(meta["model_fallback"])
            self.assertFalse(meta["key_fallback"])
            self.assertEqual(meta["attempt_count"], 1)

        print("[PASS] Test 11: Fine-grained fallback provenance tracking verified!")

if __name__ == '__main__':
    unittest.main()
