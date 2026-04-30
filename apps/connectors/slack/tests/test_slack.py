"""Slack MCP integration + sync + insight tests (mocked Slack API)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.insight_functions.slack import SlackActivity, get_slack_activity
from apps.connectors.slack.client import SlackClient
from apps.connectors.slack.integration import SlackIntegration
from apps.connectors.slack.sync import SlackSyncPipeline, run_sync
from apps.data_access.models import Credential, DataSnapshot, Integration


def _stub_slack_response(payload: dict[str, Any]) -> Any:
    resp = MagicMock()
    resp.get.side_effect = payload.get
    return resp


@pytest.mark.django_db(transaction=True)
class TestSlackClientAuth:
    def test_slack_client_auth(self) -> None:
        with schema_context("test_tenant"):
            Integration.objects.filter(provider="slack").delete()
            integration = Integration.objects.create(provider="slack", is_active=True)
            credential = Credential(integration=integration)
            credential.set_tokens({"bot_token": "xoxb-test-token"})
            credential.save()

            with patch(
                "apps.connectors.slack.client.WebClient"
            ) as mock_web_client:
                SlackClient(integration)
                mock_web_client.assert_called_once_with(token="xoxb-test-token")


@pytest.mark.django_db(transaction=True)
class TestSlackSync:
    def test_sync_channels(self) -> None:
        with schema_context("test_tenant"):
            Integration.objects.filter(provider="slack").delete()
            integration = Integration.objects.create(provider="slack", is_active=True)
            credential = Credential(integration=integration)
            credential.set_tokens({"bot_token": "xoxb-test"})
            credential.save()

            web = MagicMock()
            web.conversations_list.return_value = _stub_slack_response(
                {
                    "channels": [
                        {"id": "C1", "name": "general", "is_member": True, "num_members": 12},
                        {"id": "C2", "name": "private", "is_member": False, "num_members": 3},
                    ]
                }
            )
            web.conversations_history.return_value = _stub_slack_response(
                {
                    "messages": [
                        {"user": "U1", "ts": "1.0", "text": "hi"},
                        {"user": "U2", "ts": "2.0", "text": "yo", "thread_ts": "2.0"},
                    ]
                }
            )
            web.users_list.return_value = _stub_slack_response(
                {
                    "members": [
                        {"id": "U1", "is_bot": False, "deleted": False},
                        {"id": "U2", "is_bot": False, "deleted": False},
                        {"id": "B1", "is_bot": True, "deleted": False},
                    ]
                }
            )
            client = SlackClient(integration, web_client=web)
            pipeline = SlackSyncPipeline(client=client)

            snapshot = run_sync(days=7, pipeline=pipeline)

            assert snapshot is not None
            assert isinstance(snapshot, DataSnapshot)
            assert snapshot.source == "slack"
            channels = snapshot.metrics["channels"]["data"]["items"]
            assert len(channels) == 1
            assert channels[0]["name"] == "general"

            integration.refresh_from_db()
            assert integration.last_sync_at is not None


@pytest.mark.django_db(transaction=True)
class TestSlackInsight:
    def test_slack_insight(self) -> None:
        cache.clear()
        with schema_context("test_tenant"):
            DataSnapshot.objects.filter(source="slack").delete()
            today: date = timezone.now().date()
            DataSnapshot.objects.create(
                source="slack",
                period_start=today - timedelta(days=7),
                period_end=today,
                metrics={
                    "channels": {
                        "data": {
                            "count": 2,
                            "items": [
                                {"id": "C1", "name": "general"},
                                {"id": "C2", "name": "ops"},
                            ],
                        },
                        "ok": True,
                    },
                    "messages": {
                        "data": {
                            "total_messages": 42,
                            "active_users": 7,
                            "per_channel": {
                                "general": {"count": 30, "unique_users": 5},
                                "ops": {"count": 12, "unique_users": 3},
                            },
                            "window_days": 7,
                        },
                        "ok": True,
                    },
                    "users": {"data": {"total": 10, "humans": 8, "bots": 2}, "ok": True},
                },
            )

            activity = get_slack_activity(period_days=7)

        assert isinstance(activity, SlackActivity)
        assert activity.total_messages == 42
        assert activity.active_users == 7
        assert activity.channel_count == 2
        assert activity.top_channels[0]["name"] == "general"
        assert 0.0 <= activity.bot_ratio <= 1.0
        assert activity.data_quality in {"high", "partial", "low"}

    def test_slack_insight_raises_without_data(self) -> None:
        cache.clear()
        with schema_context("test_tenant"):
            DataSnapshot.objects.filter(source="slack").delete()
            with pytest.raises(InsufficientData):
                get_slack_activity(period_days=1)


def test_slack_integration_advertises_provider() -> None:
    assert SlackIntegration.provider == "slack"
