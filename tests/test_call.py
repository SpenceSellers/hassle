import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from click.testing import CliRunner

from hassle import api
from hassle.main import cli


class CallTests(unittest.TestCase):
    def test_notification_skips_states_and_posts_only_params(self):
        requests = []

        def handle(request):
            requests.append(request)
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/api/services/notify/mobile_app_phone")
            import json
            self.assertEqual(json.loads(request.content), {
                "message": "Hello world", "data": {"ttl": 0},
            })
            return httpx.Response(200, json=[])

        client = httpx.Client(base_url="http://ha.test/api", transport=httpx.MockTransport(handle))
        with patch.object(api, "get_client", return_value=client):
            result = CliRunner().invoke(cli, [
                "call", "--no-target", "notify/mobile_app_phone",
                "message=Hello world", 'data={"ttl":0}',
            ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.output, "Called notify/mobile_app_phone.\n")
        self.assertEqual(len(requests), 1)

    def test_no_target_rejects_filters_before_any_api_call(self):
        with patch.object(api, "get_states") as states, patch.object(api, "call_service") as call:
            result = CliRunner().invoke(cli, ["call", "--no-target", "notify/mobile_app_phone", "phone"])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("--no-target cannot be used with entity filters", result.output)
        states.assert_not_called()
        call.assert_not_called()

    def test_no_target_allows_empty_params(self):
        with patch.object(api, "get_states") as states, patch.object(api, "call_service") as call:
            result = CliRunner().invoke(cli, ["call", "--no-target", "script/run"])
        self.assertEqual(result.exit_code, 0, result.output)
        states.assert_not_called()
        call.assert_called_once_with("script", "run", None, {})

    def test_default_still_resolves_entity(self):
        entity = SimpleNamespace(entity_id="light.kitchen", attributes={})
        with patch.object(api, "get_states", return_value=[entity]), patch.object(api, "call_service") as call:
            result = CliRunner().invoke(cli, ["call", "light/turn_on", "kitchen", "brightness=200"])
        self.assertEqual(result.exit_code, 0, result.output)
        call.assert_called_once_with("light", "turn_on", "light.kitchen", {"brightness": 200})
        self.assertEqual(result.output, "Called light/turn_on on light.kitchen.\n")

    def test_targeted_api_payload_still_includes_entity_id(self):
        def handle(request):
            import json
            self.assertEqual(json.loads(request.content), {"entity_id": "light.kitchen", "brightness": 200})
            return httpx.Response(200, json=[])

        client = httpx.Client(base_url="http://ha.test/api", transport=httpx.MockTransport(handle))
        with patch.object(api, "get_client", return_value=client):
            self.assertEqual(api.call_service("light", "turn_on", "light.kitchen", {"brightness": 200}), [])


if __name__ == "__main__":
    unittest.main()
