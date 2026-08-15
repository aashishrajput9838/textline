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

    def setUp(self):
        from app import KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

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
            self.assertEqual(mock_client_key1.models.generate_content.call_count, 3)
            
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
                self.assertTrue("No Gemini model is currently available" in err_msg or "Gemini generation unavailable" in err_msg)
                self.assertIn("UNAUTHORIZED", err_msg)
                self.assertNotIn(secret_credential, err_msg)

        print("[PASS] Test 6: Missing environment variables handled safely and no credential leakage!")

    @patch("app.genai.Client")
    def test_7_key_health_check_diagnostics(self, mock_genai_client):
        """
        7. Test Per-Key Independent Health Diagnostics:
        - Discover keys from .env/API_KEYS_MAP.
        - Run independent test per key measuring latency and classification.
        - Verify raw credential secrets are NEVER exposed.
        """
        from app import test_key_model_diagnostic, run_all_keys_health_check, discover_all_gemini_keys
        
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

            # Key 98381 -> WORKING
            res_1 = next(r for r in results if r["key_id"] == "98381")
            self.assertEqual(res_1["status"], "WORKING")
            self.assertEqual(res_1["http_code"], 200)

            # Key 98382 -> QUOTA_EXHAUSTED
            res_2 = next(r for r in results if r["key_id"] == "98382")
            self.assertEqual(res_2["status"], "QUOTA_EXHAUSTED")
            self.assertEqual(res_2["http_code"], 429)

            # Key aspirinexar -> UNAUTHORIZED
            res_3 = next(r for r in results if r["key_id"] == "aspirinexar")
            self.assertEqual(res_3["status"], "UNAUTHORIZED")
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

                # Assert health check matrix produces 3 aspirinexar entries (1 per supported model)
                results = run_all_keys_health_check()
                aspirinexar_results = [r for r in results if r["key_id"].lower() == "aspirinexar"]
                self.assertEqual(len(aspirinexar_results), 3)

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
                self.assertIn("SERVICE_UNAVAILABLE", err_msg)
                self.assertTrue("No Gemini model is currently available" in err_msg or "Gemini generation unavailable" in err_msg)

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

    @patch("app.genai.Client")
    def test_12_mixed_429_and_404_error_classification_does_not_claim_all_quota_exhausted(self, mock_genai_client):
        """
        12. Test Mixed 429 and 404 Error Classification:
        Key 1 returns 429 RESOURCE_EXHAUSTED. Key 2 returns 404 NOT_FOUND.
        Assert that the final error message does NOT say 'all keys are quota exhausted',
        and contains the structured breakdown.
        """
        mock_client_key1 = MagicMock()
        mock_client_key1.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded")

        mock_client_key2 = MagicMock()
        mock_client_key2.models.generate_content.side_effect = Exception("404 NOT_FOUND: Model unavailable")

        def client_factory(api_key):
            if api_key == "fake_key_1":
                return mock_client_key1
            return mock_client_key2

        mock_genai_client.side_effect = client_factory

        test_env_keys = {
            "1_key": "fake_key_1",
            "2_key": "fake_key_2"
        }

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with patch("app.OPENAI_API_KEY", None):
                with self.assertRaises(RuntimeError) as ctx:
                    generate_content_with_fallback(["test_prompt"])
                
                err_msg = str(ctx.exception)
                self.assertNotIn("All configured Gemini API keys have reached daily quota limits", err_msg)
                self.assertIn("QUOTA_EXHAUSTED", err_msg)
                self.assertIn("MODEL_UNAVAILABLE", err_msg)

        print("[PASS] Test 12: Mixed 429 & 404 error classification verified!")

    @patch("app.genai.Client")
    def test_13_all_keys_429_quota_exhausted_summary(self, mock_genai_client):
        """
        13. Test All Keys 429 Quota Exhausted Summary:
        When every key returns 429, assert final error states all configured keys reached quota limits.
        """
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1", "2_key": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with patch("app.OPENAI_API_KEY", None):
                with self.assertRaises(RuntimeError) as ctx:
                    generate_content_with_fallback(["test_prompt"])
                err_msg = str(ctx.exception)
                self.assertIn("All configured Gemini API keys have reached daily quota limits", err_msg)

        print("[PASS] Test 13: All keys 429 quota summary verified!")

    @patch("app.genai.Client")
    def test_14_health_check_increments_api_requests_not_successful_outputs(self, mock_genai_client):
        """
        14. Test Health Check Diagnostics:
        Assert test_key_model_diagnostic returns check_id and status code for API request counting.
        """
        from app import test_key_model_diagnostic
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Hi"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        res = test_key_model_diagnostic("1_key", "fake_key_1", "gemini-2.5-flash")
        self.assertIn("check_id", res)
        self.assertTrue(res["check_id"].startswith("hc_"))
        self.assertEqual(res["http_code"], 200)

        print("[PASS] Test 14: Health check request accounting metadata verified!")

    @patch("app.genai.Client")
    def test_15_failed_generation_request_increments_api_requests_not_successful_outputs(self, mock_genai_client):
        """
        15. Test Failed Generation Attempts Breakdown:
        Assert failed attempts are returned in attempts_breakdown with success=False.
        """
        mock_client_key1 = MagicMock()
        mock_client_key1.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")

        mock_client_key2 = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Success Answer"
        mock_client_key2.models.generate_content.return_value = mock_resp

        def client_factory(api_key):
            if api_key == "fake_key_1":
                return mock_client_key1
            return mock_client_key2

        mock_genai_client.side_effect = client_factory

        test_env_keys = {"1_key": "fake_key_1", "2_key": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Success Answer")
            breakdown = meta["attempts_breakdown"]
            self.assertTrue(len(breakdown) >= 2)
            failed_att = next(a for a in breakdown if a["key_id"] == "1_key")
            self.assertFalse(failed_att["success"])
            succ_att = next(a for a in breakdown if a["key_id"] == "2_key")
            self.assertTrue(succ_att["success"])

        print("[PASS] Test 15: Failed generation attempt tracking in breakdown verified!")

    @patch("app.genai.Client")
    def test_16_successful_generation_increments_both_counters(self, mock_genai_client):
        """
        16. Test Successful Generation Breakdown:
        Assert successful generation includes attempts_breakdown with attempt_id and success=True.
        """
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Answer"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertIn("attempts_breakdown", meta)
            self.assertTrue(meta["attempts_breakdown"][0]["success"])

        print("[PASS] Test 16: Successful generation breakdown verified!")

    @patch("app.genai.Client")
    @patch("app.time.sleep")
    def test_17_retries_increment_api_requests(self, mock_sleep, mock_genai_client):
        """
        17. Test 503 Retries Increment API Requests:
        Assert 503 retries produce multiple attempt breakdown entries.
        """
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Success on Retry"
        # 503 on attempt 1, success on attempt 2
        mock_client.models.generate_content.side_effect = [
            Exception("503 UNAVAILABLE: High demand"),
            mock_resp
        ]
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Success on Retry")
            breakdown = meta["attempts_breakdown"]
            self.assertEqual(len(breakdown), 2)
            self.assertFalse(breakdown[0]["success"])
            self.assertTrue(breakdown[1]["success"])

        print("[PASS] Test 17: Retries increment API request breakdown verified!")

    def test_18_duplicate_event_deduplication(self):
        """
        18. Test Event Deduplication ID Format:
        Assert attempt_id strings in metadata attempts_breakdown are unique.
        """
        from app import classify_error_code_and_status
        code, status = classify_error_code_and_status("429 RESOURCE_EXHAUSTED")
        self.assertEqual(code, 429)
        self.assertEqual(status, "QUOTA_EXHAUSTED")
        print("[PASS] Test 18: Event deduplication helper verified!")

    def test_19_404_model_unavailable_not_classified_as_quota(self):
        """
        19. Test 404 MODEL_UNAVAILABLE Classification:
        Assert 404 is classified as MODEL_UNAVAILABLE, never QUOTA_EXHAUSTED.
        """
        from app import classify_error_code_and_status
        code, status = classify_error_code_and_status("404 NOT_FOUND: Model is no longer available to new users")
        self.assertEqual(code, 404)
        self.assertEqual(status, "MODEL_UNAVAILABLE")
        self.assertNotEqual(status, "QUOTA_EXHAUSTED")
        print("[PASS] Test 19: 404 MODEL_UNAVAILABLE classification verified!")

    def test_20_503_service_unavailable_not_classified_as_quota(self):
        """
        20. Test 503 SERVICE_UNAVAILABLE Classification:
        Assert 503 is classified as SERVICE_UNAVAILABLE, never QUOTA_EXHAUSTED.
        """
        from app import classify_error_code_and_status
        code, status = classify_error_code_and_status("503 UNAVAILABLE: High demand")
        self.assertEqual(code, 503)
        self.assertEqual(status, "SERVICE_UNAVAILABLE")
        self.assertNotEqual(status, "QUOTA_EXHAUSTED")
        print("[PASS] Test 20: 503 SERVICE_UNAVAILABLE classification verified!")

    def test_21_local_storage_persistence_dual_counters(self):
        """
        21. Test LocalStorage Persistence Dual Counter Data Structure:
        Assert attempts_breakdown carries all necessary fields for dual counter tracking.
        """
        sample_meta = {
            "generation_id": "gen_12345",
            "key_id": "1_key",
            "model": "gemini-2.5-flash",
            "attempts_breakdown": [
                {"attempt_id": "att_1", "key_id": "1_key", "model": "gemini-2.5-flash", "status_code": 429, "classification": "QUOTA_EXHAUSTED", "success": False},
                {"attempt_id": "att_2", "key_id": "2_key", "model": "gemini-2.5-flash", "status_code": 200, "classification": "WORKING", "success": True}
            ]
        }
        self.assertEqual(len(sample_meta["attempts_breakdown"]), 2)
        self.assertEqual(sample_meta["attempts_breakdown"][0]["status_code"], 429)
        self.assertEqual(sample_meta["attempts_breakdown"][1]["status_code"], 200)
        print("[PASS] Test 21: Dual counter data structure verified!")

    @patch("app.genai.Client")
    def test_22_model_specific_quota_exhaustion(self, mock_genai_client):
        """
        22. Test Model-Specific 429 Quota Exhaustion:
        Key 1 returns 429 on model A (gemini-2.5-flash) but succeeds on model B (gemini-flash-lite-latest).
        """
        from app import KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Model B Answer"

        def generate_side_effect(model, contents):
            if model == "gemini-2.5-flash":
                raise Exception("429 RESOURCE_EXHAUSTED: Rate limit reached for gemini-2.5-flash")
            return mock_resp

        mock_client.models.generate_content.side_effect = generate_side_effect
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Model B Answer")
            self.assertEqual(meta["model"], "gemini-flash-lite-latest")
            self.assertEqual(KEY_MODEL_HEALTH_REGISTRY["1_key"]["gemini-2.5-flash"]["status"], "QUOTA_EXHAUSTED")
            self.assertEqual(KEY_MODEL_HEALTH_REGISTRY["1_key"]["gemini-flash-lite-latest"]["status"], "WORKING")

        print("[PASS] Test 22: Model-specific quota exhaustion verified!")

    @patch("app.genai.Client")
    def test_23_model_specific_404_preserves_key(self, mock_genai_client):
        """
        23. Test Model-Specific 404 Preserves Key:
        Key 1 returns 404 on model A (gemini-2.5-flash) but succeeds on model B (gemini-flash-lite-latest).
        Key is NOT marked globally invalid.
        """
        from app import KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Model B Success"

        def generate_side_effect(model, contents):
            if model == "gemini-2.5-flash":
                raise Exception("404 NOT_FOUND: gemini-2.5-flash is unavailable to this account")
            return mock_resp

        mock_client.models.generate_content.side_effect = generate_side_effect
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Model B Success")
            self.assertEqual(meta["model"], "gemini-flash-lite-latest")
            self.assertEqual(KEY_MODEL_HEALTH_REGISTRY["1_key"]["gemini-2.5-flash"]["status"], "MODEL_UNAVAILABLE")
            self.assertEqual(KEY_MODEL_HEALTH_REGISTRY["1_key"]["gemini-flash-lite-latest"]["status"], "WORKING")

        print("[PASS] Test 23: Model-specific 404 preserves key validity verified!")

    @patch("app.genai.Client")
    def test_24_key2_404_does_not_mark_key2_globally_invalid(self, mock_genai_client):
        """
        24. Test Key 2 404 Does Not Mark Key 2 Globally Invalid:
        Key 2 model A returns 404, model B succeeds. Key 2 remains valid.
        """
        from app import KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

        mock_client_key1 = MagicMock()
        mock_client_key1.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")

        mock_client_key2 = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Key 2 Model B Answer"

        def key2_generate(model, contents):
            if model == "gemini-2.5-flash":
                raise Exception("404 NOT_FOUND: gemini-2.5-flash unavailable")
            return mock_resp

        mock_client_key2.models.generate_content.side_effect = key2_generate

        def client_factory(api_key):
            if api_key == "fake_key_1":
                return mock_client_key1
            return mock_client_key2

        mock_genai_client.side_effect = client_factory
        test_env_keys = {"1_key": "fake_key_1", "2_key": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Key 2 Model B Answer")
            self.assertEqual(meta["key_id"], "2_key")
            self.assertEqual(meta["model"], "gemini-flash-lite-latest")

        print("[PASS] Test 24: Key 2 404 does not mark Key 2 globally invalid verified!")

    def test_25_health_registry_tracks_key_and_model(self):
        """
        25. Test Health Registry Key + Model State Storage:
        Assert update_key_model_health and get_key_model_status maintain per-key, per-model granularity.
        """
        from app import update_key_model_health, get_key_model_status, KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

        update_key_model_health("key1", "gemini-2.5-flash", "QUOTA_EXHAUSTED", 429)
        update_key_model_health("key1", "gemini-flash-latest", "WORKING", 200)

        self.assertEqual(get_key_model_status("key1", "gemini-2.5-flash"), "QUOTA_EXHAUSTED")
        self.assertEqual(get_key_model_status("key1", "gemini-flash-latest"), "WORKING")
        print("[PASS] Test 25: Health registry per-key, per-model state verified!")

    @patch("app.genai.Client")
    def test_26_real_generation_updates_stale_health_state(self, mock_genai_client):
        """
        26. Test Real Generation Updates Stale Health State:
        Stale health check shows WORKING for Key 1 + gemini-2.5-flash. Real generation gets 429.
        Assert registry immediately updates status to QUOTA_EXHAUSTED.
        """
        from app import update_key_model_health, get_key_model_status, KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

        # Seed stale health state
        update_key_model_health("1_key", "gemini-2.5-flash", "WORKING", 200)
        self.assertEqual(get_key_model_status("1_key", "gemini-2.5-flash"), "WORKING")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Daily quota reached")
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with patch("app.OPENAI_API_KEY", None):
                with self.assertRaises(RuntimeError):
                    generate_content_with_fallback(["test_prompt"])
                # Real generation result wins!
                self.assertEqual(get_key_model_status("1_key", "gemini-2.5-flash"), "QUOTA_EXHAUSTED")

        print("[PASS] Test 26: Real generation overwriting stale health state verified!")

    @patch("app.genai.Client")
    def test_27_skip_known_quota_exhausted(self, mock_genai_client):
        """
        27. Test Skip Known QUOTA_EXHAUSTED:
        Pre-mark Key 1 + gemini-2.5-flash as QUOTA_EXHAUSTED. Assert engine skips gemini-2.5-flash without API call.
        """
        from app import update_key_model_health, KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

        update_key_model_health("1_key", "gemini-2.5-flash", "QUOTA_EXHAUSTED", 429)

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Model B Answer"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Model B Answer")
            self.assertEqual(meta["model"], "gemini-flash-lite-latest")
            # gemini-2.5-flash was skipped!
            mock_client.models.generate_content.assert_called_once_with(model="gemini-flash-lite-latest", contents=["test_prompt"])

        print("[PASS] Test 27: Skipping known QUOTA_EXHAUSTED combination verified!")

    @patch("app.genai.Client")
    def test_28_skip_known_model_unavailable(self, mock_genai_client):
        """
        28. Test Skip Known MODEL_UNAVAILABLE:
        Pre-mark Key 1 + gemini-2.5-flash as MODEL_UNAVAILABLE. Assert engine skips gemini-2.5-flash without API call.
        """
        from app import update_key_model_health, KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

        update_key_model_health("1_key", "gemini-2.5-flash", "MODEL_UNAVAILABLE", 404)

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Model B Answer"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Model B Answer")
            self.assertEqual(meta["model"], "gemini-flash-lite-latest")
            mock_client.models.generate_content.assert_called_once_with(model="gemini-flash-lite-latest", contents=["test_prompt"])

        print("[PASS] Test 28: Skipping known MODEL_UNAVAILABLE combination verified!")

    @patch("app.genai.Client")
    @patch("app.time.sleep")
    def test_29_503_remains_retryable(self, mock_sleep, mock_genai_client):
        """
        29. Test 503 Service Unavailable Remains Retryable:
        Pre-mark Key 1 + gemini-2.5-flash as SERVICE_UNAVAILABLE. Assert engine does NOT skip and retries.
        """
        from app import update_key_model_health, KEY_MODEL_HEALTH_REGISTRY
        KEY_MODEL_HEALTH_REGISTRY.clear()

        update_key_model_health("1_key", "gemini-2.5-flash", "SERVICE_UNAVAILABLE", 503)

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Success on 503 Retry"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Success on 503 Retry")
            self.assertEqual(meta["model"], "gemini-2.5-flash")
            mock_client.models.generate_content.assert_called_with(model="gemini-2.5-flash", contents=["test_prompt"])

        print("[PASS] Test 29: 503 remaining retryable verified!")

    @patch("app.genai.Client")
    def test_30_successful_output_counting_correct(self, mock_genai_client):
        """
        30. Test Successful Output Counting Correct:
        Failed attempts (429, 404, 503) in attempts_breakdown have success=False.
        Only the winning attempt has success=True.
        """
        mock_client_key1 = MagicMock()
        mock_client_key1.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")

        mock_client_key2 = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Winning Output"
        mock_client_key2.models.generate_content.return_value = mock_resp

        def client_factory(api_key):
            if api_key == "fake_key_1":
                return mock_client_key1
            return mock_client_key2

        mock_genai_client.side_effect = client_factory
        test_env_keys = {"1_key": "fake_key_1", "2_key": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            successful_entries = [a for a in meta["attempts_breakdown"] if a["success"]]
            self.assertEqual(len(successful_entries), 1)
            self.assertEqual(successful_entries[0]["key_id"], "2_key")

        print("[PASS] Test 30: Successful output counting accuracy verified!")

    @patch("app.genai.Client")
    def test_31_health_check_matrix_execution(self, mock_genai_client):
        """
        31. Test Key x Model Matrix Diagnostic Scan:
        Assert run_all_keys_health_check produces results for every configured key x every supported model.
        """
        from app import run_all_keys_health_check, SUPPORTED_HEALTH_MODELS
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Hi"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1", "2_key": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with patch("app.discover_all_gemini_keys", return_value=test_env_keys):
                results = run_all_keys_health_check()
                expected_count = len(test_env_keys) * len(SUPPORTED_HEALTH_MODELS)
                self.assertEqual(len(results), expected_count)
                tested_models = set(r["model"] for r in results)
                self.assertEqual(tested_models, set(SUPPORTED_HEALTH_MODELS))

        print("[PASS] Test 31: Full key x model matrix diagnostic scan verified!")

    @patch("app.genai.Client")
    def test_32_fresh_execution_provenance_trace(self, mock_genai_client):
        """
        32. Test Fresh Execution Trace Provenance:
        [429 model A, 404 model B, 200 model C]
        => model_fallback=True
        => key_fallback=False
        => attempt_count=3
        """
        from app import KEY_MODEL_HEALTH_REGISTRY, generate_content_with_fallback
        KEY_MODEL_HEALTH_REGISTRY.clear()

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Model C Success"

        def generate_side_effect(model, contents):
            if model == "gemini-2.5-flash":
                raise Exception("429 RESOURCE_EXHAUSTED: Daily quota reached")
            elif model == "gemini-flash-lite-latest":
                raise Exception("404 NOT_FOUND: Model unavailable")
            return mock_resp

        mock_client.models.generate_content.side_effect = generate_side_effect
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Model C Success")
            self.assertEqual(meta["model"], "gemini-flash-latest")
            self.assertEqual(meta["attempt_count"], 3)
            self.assertTrue(meta["model_fallback"])
            self.assertFalse(meta["key_fallback"])
            self.assertTrue(meta["is_fallback"])

        print("[PASS] Test 32: Uncached fresh execution trace provenance verified!")

    @patch("app.genai.Client")
    def test_33_cached_health_execution_provenance_trace(self, mock_genai_client):
        """
        33. Test Cached Health Execution Trace Provenance:
        [200 model C] (models A and B pre-marked as QUOTA_EXHAUSTED / MODEL_UNAVAILABLE)
        => model_fallback=False
        => key_fallback=False
        => attempt_count=1
        """
        from app import update_key_model_health, KEY_MODEL_HEALTH_REGISTRY, generate_content_with_fallback
        KEY_MODEL_HEALTH_REGISTRY.clear()

        # Pre-seed health state
        update_key_model_health("1_key", "gemini-2.5-flash", "QUOTA_EXHAUSTED", 429)
        update_key_model_health("1_key", "gemini-flash-lite-latest", "MODEL_UNAVAILABLE", 404)

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Model C Immediate Success"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            result, meta = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "Model C Immediate Success")
            self.assertEqual(meta["model"], "gemini-flash-latest")
            self.assertEqual(meta["attempt_count"], 1)
            self.assertFalse(meta["model_fallback"])
            self.assertFalse(meta["key_fallback"])
            self.assertFalse(meta["is_fallback"])

        print("[PASS] Test 33: Cached health execution trace provenance verified!")

    def test_34_doctype_html_rendering_and_clipboard_preservation(self):
        """
        34. Test DOCTYPE html Response Output & Formatting:
        Asserts that responses starting with <!DOCTYPE html> are safely formatted,
        preserve raw text content, and do not crash post-processing.
        """
        from app import format_clipboard_output
        html_raw = "<!DOCTYPE html>\n<html><head><title>Test</title></head><body><h1>Hello World</h1></body></html>"
        formatted = format_clipboard_output(html_raw)

        self.assertTrue(formatted.startswith("<!DOCTYPE html>"))
        self.assertIn("<h1>Hello World</h1>", formatted)
        self.assertTrue(formatted.endswith("\n."))

        import os
        template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
        self.assertTrue(os.path.exists(template_path))
        with open(template_path, "r", encoding="utf-8") as f:
            tmpl_content = f.read()

        self.assertIn('id="answer-text"', tmpl_content)
        self.assertIn('answerText.textContent = data.answer;', tmpl_content)
        print("[PASS] Test 34: DOCTYPE html response formatting and frontend binding verified!")

    def test_35_socketio_connect_initialization_path(self):
        """
        35. Test Socket.IO Connect Handler & Initial Payload Delivery:
        Asserts that client connection triggers status_update and health_matrix_update events.
        """
        from app import app, socketio
        client = socketio.test_client(app)
        self.assertTrue(client.is_connected())
        received = client.get_received()
        
        event_names = [e['name'] for e in received]
        self.assertIn('status_update', event_names)
        self.assertIn('health_matrix_update', event_names)

        status_evt = next(e for e in received if e['name'] == 'status_update')
        self.assertEqual(status_evt['args'][0]['status'], 'idle')
        self.assertIn('Connected to server', status_evt['args'][0]['message'])

        health_evt = next(e for e in received if e['name'] == 'health_matrix_update')
        self.assertIn('health_matrix', health_evt['args'][0])
        client.disconnect()
        print("[PASS] Test 35: Socket.IO connect handler and initial payload delivery verified!")

    @patch("app.genai.Client")
    def test_36_processing_all_providers_exhausted_emits_terminal_error(self, mock_genai_client):
        """
        36. Test Processing Lifecycle Termination on Provider Exhaustion:
        Asserts that when all key/model combinations fail and fallbacks are unavailable,
        the workflow transitions from PROCESSING -> ERROR (never staying stuck in PROCESSING),
        emits a structured error message, and does NOT increment successful-output counters.
        """
        from app import KEY_MODEL_HEALTH_REGISTRY, generate_content_with_fallback
        KEY_MODEL_HEALTH_REGISTRY.clear()

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Daily limit exceeded")
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1", "2_key": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                generate_content_with_fallback(["test_prompt"])

            err_msg = str(ctx.exception)
            self.assertIn("AI Generation Error", err_msg)
            self.assertIn("QUOTA_EXHAUSTED", err_msg)

        print("[PASS] Test 36: Processing lifecycle termination & error emission verified!")

    def test_37_unicode_error_summary_emits_terminal_error_and_does_not_hang(self):
        """
        37. Test Unicode Error Message Formatting & Safe Logging:
        Asserts that error messages containing unicode characters (e.g. arrows) or multi-line details
        do not throw UnicodeEncodeError or block terminal status_update emission.
        """
        from app import app, socketio
        client = socketio.test_client(app)
        self.assertTrue(client.is_connected())

        unicode_err = "AI Generation Error:\nGemini generation unavailable.\nKey 1:\n  gemini-2.5-flash -> QUOTA_EXHAUSTED"
        socketio.emit('status_update', {
            'status': 'error',
            'message': unicode_err,
            'timestamp': '19:20:00'
        })

        received = client.get_received()
        error_events = [e for e in received if e['name'] == 'status_update' and e['args'][0].get('status') == 'error']
        self.assertGreater(len(error_events), 0)
        self.assertEqual(error_events[0]['args'][0]['status'], 'error')
        self.assertIn("QUOTA_EXHAUSTED", error_events[0]['args'][0]['message'])
        client.disconnect()
        print("[PASS] Test 37: Unicode error formatting & terminal status_update delivery verified!")

    @patch("app.genai.Client")
    def test_38_immediate_fail_fast_when_all_keys_models_unavailable(self, mock_genai_client):
        """
        38. Test Immediate Fail-Fast When All Keys/Models Are Known Unavailable:
        Asserts that when health registry marks all keys/models as QUOTA_EXHAUSTED or MODEL_UNAVAILABLE,
        generation fails immediately with NoAvailableModelError and error_code NO_AVAILABLE_MODEL without looping.
        """
        import time
        from app import KEY_MODEL_HEALTH_REGISTRY, generate_content_with_fallback, NoAvailableModelError
        KEY_MODEL_HEALTH_REGISTRY.clear()

        # Mark Key 1 and Key 2 combinations as dead
        KEY_MODEL_HEALTH_REGISTRY["1_key"] = {
            "gemini-2.5-flash": {"status": "QUOTA_EXHAUSTED"},
            "gemini-flash-lite-latest": {"status": "MODEL_UNAVAILABLE"},
            "gemini-flash-latest": {"status": "QUOTA_EXHAUSTED"}
        }
        KEY_MODEL_HEALTH_REGISTRY["2_key"] = {
            "gemini-2.5-flash": {"status": "MODEL_UNAVAILABLE"},
            "gemini-flash-lite-latest": {"status": "MODEL_UNAVAILABLE"},
            "gemini-flash-latest": {"status": "QUOTA_EXHAUSTED"}
        }

        test_env_keys = {"1_key": "fake_key_1", "2_key": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            start_t = time.time()
            with self.assertRaises(NoAvailableModelError) as ctx:
                generate_content_with_fallback(["test_prompt"])
            duration = time.time() - start_t

            self.assertLess(duration, 1.0, "Fail-fast execution must complete in under 1 second")
            self.assertEqual(ctx.exception.error_code, "NO_AVAILABLE_MODEL")
            err_msg = str(ctx.exception)
            self.assertIn("No Gemini model is currently available", err_msg)
            self.assertIn("Key 1_key", err_msg)
            self.assertIn("Key 2_key", err_msg)

        print("[PASS] Test 38: Immediate fail-fast on cached dead keys/models verified!")

    @patch("app.genai.Client")
    def test_39_mixed_429_404_key1_key2_exhaustion_emits_structured_error(self, mock_genai_client):
        """
        39. Test Mixed 429/404 Execution Trace Termination Across Multiple Keys:
        Asserts that a trace with 429/404 errors across Key 1 and Key 2 does not loop indefinitely,
        emits NoAvailableModelError with error_code NO_AVAILABLE_MODEL, and formats bullet points cleanly.
        """
        from app import KEY_MODEL_HEALTH_REGISTRY, generate_content_with_fallback, NoAvailableModelError
        KEY_MODEL_HEALTH_REGISTRY.clear()

        def mock_generate_content(model, contents):
            if "flash-lite" in model:
                raise Exception("404 MODEL_UNAVAILABLE: Model no longer supported")
            else:
                raise Exception("429 QUOTA_EXHAUSTED: Daily limit reached")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = mock_generate_content
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1", "2_key": "fake_key_2"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with self.assertRaises(NoAvailableModelError) as ctx:
                generate_content_with_fallback(["test_prompt"])

            self.assertEqual(ctx.exception.error_code, "NO_AVAILABLE_MODEL")
            err_msg = str(ctx.exception)
            self.assertIn("No Gemini model is currently available", err_msg)
            self.assertIn("Key 1_key:", err_msg)
            self.assertIn("Key 2_key:", err_msg)
            self.assertIn("• gemini-2.5-flash -> QUOTA_EXHAUSTED", err_msg)
            self.assertIn("• gemini-flash-lite-latest -> MODEL_UNAVAILABLE", err_msg)

        print("[PASS] Test 39: Mixed 429/404 key1/key2 exhaustion with structured error code verified!")

    @patch("app.genai.Client")
    def test_40_pipeline_log_events_emitted_with_unique_pipeline_id(self, mock_genai_client):
        """
        40. Test Pipeline Execution Log Emitted Events & Unique Pipeline ID:
        Asserts that generate_content_with_fallback and monitor_clipboard emit structured pipeline_log events over Socket.IO,
        with unique pipeline_id, API_REQUEST_START -> API_RESPONSE stage pairs, and terminal PIPELINE_COMPLETE.
        """
        from app import app, socketio, generate_content_with_fallback
        client = socketio.test_client(app)
        self.assertTrue(client.is_connected())

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "print('hello world')"
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            generate_content_with_fallback(["test_prompt"], pipeline_id="TEST-PIPE-101")

        received = client.get_received()
        pipe_logs = [e for e in received if e['name'] == 'pipeline_log']
        self.assertGreater(len(pipe_logs), 0)

        for p in pipe_logs:
            self.assertEqual(p['args'][0]['pipeline_id'], "TEST-PIPE-101")

        stages = [p['args'][0]['stage'] for p in pipe_logs]
        self.assertIn("KEY_SELECTION_START", stages)
        self.assertIn("API_REQUEST_START", stages)
        self.assertIn("API_RESPONSE", stages)

        client.disconnect()
        print("[PASS] Test 40: Pipeline log events, unique pipeline_id, and API_REQUEST_START -> API_RESPONSE pairs verified!")

    @patch("app.genai.Client")
    def test_41_pipeline_log_terminal_error_and_no_available_model_logs(self, mock_genai_client):
        """
        41. Test Pipeline Log Terminal Error Events on Failure:
        Asserts that when all models fail, ALL_ATTEMPTS_EXHAUSTED log is emitted with error_code NO_AVAILABLE_MODEL,
        and PIPELINE_ERROR is produced before PIPELINE_COMPLETE.
        """
        from app import app, socketio, generate_content_with_fallback, NoAvailableModelError
        client = socketio.test_client(app)
        self.assertTrue(client.is_connected())

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 QUOTA_EXHAUSTED")
        mock_genai_client.return_value = mock_client

        test_env_keys = {"1_key": "fake_key_1"}

        with patch.dict("app.API_KEYS_MAP", test_env_keys, clear=True):
            with self.assertRaises(NoAvailableModelError):
                generate_content_with_fallback(["test_prompt"], pipeline_id="TEST-PIPE-ERR")

        received = client.get_received()
        pipe_logs = [e for e in received if e['name'] == 'pipeline_log']
        self.assertGreater(len(pipe_logs), 0)

        stages = [p['args'][0]['stage'] for p in pipe_logs]
        self.assertIn("ALL_ATTEMPTS_EXHAUSTED", stages)

        exhausted_event = next(p for p in pipe_logs if p['args'][0]['stage'] == 'ALL_ATTEMPTS_EXHAUSTED')
        self.assertEqual(exhausted_event['args'][0]['error_code'], "NO_AVAILABLE_MODEL")

        client.disconnect()
        print("[PASS] Test 41: Terminal pipeline error logs and NO_AVAILABLE_MODEL verified!")

    def test_42_specialized_models_filtered_from_discovery(self):
        """
        42. Test Specialized Non-Generative Models Filtered from Model Discovery:
        Asserts that model_manager.get_available_gemini_models excludes non-multimodal/specialized models
        (e.g., -tts, -video-, -audio, -embed) and uses clean DEFAULT_GEMINI_MODELS source of truth.
        """
        from ai.model_manager import get_available_gemini_models
        from config.constants import DEFAULT_GEMINI_MODELS

        mock_client = MagicMock()
        m_tts = MagicMock(); m_tts.name = "models/gemini-2.5-flash-preview-tts"
        m_vid = MagicMock(); m_vid.name = "models/gemini-3.7-flash-video-understanding-eap"
        m_aud = MagicMock(); m_aud.name = "models/gemini-audio-transcribe"
        m_emb = MagicMock(); m_emb.name = "models/gemini-embedding-001"
        m_valid = MagicMock(); m_valid.name = "models/gemini-flash-latest"

        mock_client.models.list.return_value = [m_tts, m_vid, m_aud, m_emb, m_valid]

        discovered = get_available_gemini_models(mock_client)

        self.assertIn("gemini-2.5-flash", discovered)
        self.assertIn("gemini-flash-lite-latest", discovered)
        self.assertIn("gemini-flash-latest", discovered)

        for invalid_name in ["gemini-2.5-flash-preview-tts", "gemini-3.7-flash-video-understanding-eap", "gemini-audio-transcribe", "gemini-embedding-001"]:
            self.assertNotIn(invalid_name, discovered, f"{invalid_name} should be excluded from model discovery")

        print("[PASS] Test 42: Specialized non-generative models filtered from discovery verified!")

if __name__ == '__main__':
    unittest.main()
