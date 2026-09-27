from unittest.mock import Mock, patch

from apps.integrations_chat.services import send_discord_message, send_slack_message


class TestChatServices:
    def test_send_slack_message_success(self):
        with patch("apps.integrations_chat.services.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200, text="ok")
            success, code, _ = send_slack_message("https://slack.com/webhook", "Hello")
            assert success is True
            assert code == 200
            mock_post.assert_called_once_with("https://slack.com/webhook", json={"text": "Hello"}, timeout=10, allow_redirects=False)

    def test_send_slack_message_blocks(self):
        with patch("apps.integrations_chat.services.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200, text="ok")
            send_slack_message("https://slack.com/webhook", "Hello", blocks=[{"type": "section"}])
            payload = mock_post.call_args[1]["json"]
            assert payload["blocks"] == [{"type": "section"}]

    def test_send_slack_message_error(self):
        with patch("apps.integrations_chat.services.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=500, text="error")
            success, code, _ = send_slack_message("https://slack.com/webhook", "Hello")
            assert success is False
            assert code == 500

    def test_send_slack_message_exception(self):
        with patch("apps.integrations_chat.services.requests.post") as mock_post:
            mock_post.side_effect = Exception("network error")
            success, code, text = send_slack_message("https://slack.com/webhook", "Hello")
            assert success is False
            assert code is None
            assert text == "Connection error"

    def test_send_discord_message_success(self):
        with patch("apps.integrations_chat.services.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=204, text="")
            success, code, _ = send_discord_message("https://discord.com/webhook", "Hello")
            assert success is True
            assert code == 204

    def test_send_discord_message_embeds(self):
        with patch("apps.integrations_chat.services.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200, text="ok")
            send_discord_message("https://discord.com/webhook", "Hello", embeds=[{"title": "T"}])
            payload = mock_post.call_args[1]["json"]
            assert payload["embeds"] == [{"title": "T"}]

    def test_send_discord_message_error(self):
        with patch("apps.integrations_chat.services.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=400, text="bad")
            success, code, _ = send_discord_message("https://discord.com/webhook", "Hello")
            assert success is False
            assert code == 400

    def test_send_discord_message_exception(self):
        with patch("apps.integrations_chat.services.requests.post") as mock_post:
            mock_post.side_effect = Exception("timeout")
            success, code, text = send_discord_message("https://discord.com/webhook", "Hello")
            assert success is False
            assert code is None
            assert text == "Connection error"
