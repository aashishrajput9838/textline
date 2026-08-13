import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Import functions to test from app.py
from app import (
    format_clipboard_output,
    generate_content_with_fallback,
    generate_content_openai_fallback,
    API_KEYS_MAP
)

class TestFallbackSystem(unittest.TestCase):

    def test_1_post_processing_padding_preservation(self):
        """
        Test 1: Post-Processing Padding Preservation
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

        print("[PASS] Test 1: 50 empty lines and dot preservation verified successfully!")

    @patch("app.genai.Client")
    def test_2_fail_fast_on_404_error(self, mock_genai_client):
        """
        Test 2: Fail-Fast on 404 NOT_FOUND / 400 INVALID_ARGUMENT
        Simulate Key 1 returning a 404 NOT_FOUND error.
        Assert that the system instantly skips Key 1 without retrying remaining models on Key 1, 
        and rotates to Key 2.
        """
        # Key 1 mock: raises 404 NOT_FOUND
        mock_client_key1 = MagicMock()
        mock_client_key1.models.generate_content.side_effect = Exception("404 NOT_FOUND: Model no longer available to new users")

        # Key 2 mock: returns valid response
        mock_client_key2 = MagicMock()
        mock_response_key2 = MagicMock()
        mock_response_key2.text = "def solution_from_key2(): pass"
        mock_client_key2.models.generate_content.return_value = mock_response_key2

        def client_factory(api_key):
            if api_key == API_KEYS_MAP["98381"]:
                return mock_client_key1
            return mock_client_key2

        mock_genai_client.side_effect = client_factory

        result = generate_content_with_fallback(["test_prompt"])

        # Assert result came from Key 2
        self.assertEqual(result, "def solution_from_key2(): pass")
        # Assert Key 1 was only called ONCE before fail-fast skipping
        self.assertEqual(mock_client_key1.models.generate_content.call_count, 1)

        print("[PASS] Test 2: Instant fail-fast skip on 404 error verified successfully!")

    @patch("app.genai.Client")
    def test_3_missing_openai_key_graceful_handling(self, mock_genai_client):
        """
        Test 3: Missing OpenAI Key Graceful Handling
        Simulate ALL Gemini keys failing and OPENAI_API_KEY missing/unconfigured.
        Assert it logs a clean warning and raises a RuntimeError instead of crashing Python.
        """
        # All Gemini clients fail
        mock_failing_client = MagicMock()
        mock_failing_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
        mock_genai_client.return_value = mock_failing_client

        with patch("app.OPENAI_API_KEY", "YOUR_OPENAI_API_KEY"):
            with self.assertRaises(RuntimeError) as ctx:
                generate_content_with_fallback(["test_prompt"], base64_image_url="data:image/png;base64,12345")

            # Assert error message details
            self.assertIn("All Gemini API keys & OpenAI fallbacks failed", str(ctx.exception))

        print("[PASS] Test 3: Graceful handling of missing OPENAI_API_KEY verified successfully!")

if __name__ == '__main__':
    unittest.main()
