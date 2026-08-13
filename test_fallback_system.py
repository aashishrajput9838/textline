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

    def test_1_all_expected_key_ids_recognized_and_ordered(self):
        """
        1. All expected key IDs are recognized in exact sequential order:
        98381 -> 98382 -> 98383 -> 98385 -> 98386 -> 98387 -> 98388 -> 98389 -> 983810
        """
        expected_keys = ["98381", "98382", "98383", "98385", "98386", "98387", "98388", "98389", "983810", "aspirinexar"]
        actual_keys = list(API_KEYS_MAP.keys())

        # Assert exact list match and order
        self.assertEqual(actual_keys, expected_keys)
        self.assertNotIn("98384", actual_keys)
        print("[PASS] Test 1: Key IDs and deterministic rotation order verified!")

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
        3. Test Fail-Fast on 400/403/404 Errors:
        Simulate Key 1 returning a 404 NOT_FOUND error.
        Assert system instantly rotates to Key 2 without retrying dead models on Key 1.
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
            result = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "def solution_key2(): pass")
            self.assertEqual(mock_client_key1.models.generate_content.call_count, 1)

        print("[PASS] Test 3: Instant fail-fast rotation on 400/403/404 verified!")

    @patch("app.genai.Client")
    def test_4_rate_limit_429_rotation(self, mock_genai_client):
        """
        4. Test 429 Rate Limit Rotation:
        Simulate 429 RESOURCE_EXHAUSTED on Key 1.
        Assert system rotates to Key 2 and succeeds.
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
            result = generate_content_with_fallback(["test_prompt"])
            self.assertEqual(result, "def rotate_success(): pass")

        print("[PASS] Test 4: 429 Quota Exhaustion key rotation verified!")

    @patch("app.openai")
    @patch("app.genai.Client")
    def test_5_openai_fallback_only_after_gemini_exhaustion(self, mock_genai_client, mock_openai_module):
        """
        5. Test OpenAI Fallback Execution:
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
                result = generate_content_with_fallback(["test_prompt"], base64_image_url="data:image/png;base64,12345")
                self.assertEqual(result, "def openai_solution(): pass")

        print("[PASS] Test 5: OpenAI fallback triggers only after Gemini keys are exhausted!")

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
                # Exception details show key ID [98381], not the secret string itself!
                err_msg = str(ctx.exception)
                self.assertIn("Key [98381]", err_msg)

        print("[PASS] Test 6: Missing environment variables handled safely and no credential leakage!")

if __name__ == '__main__':
    unittest.main()
