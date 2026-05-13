from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors._framework.models import SyncStatus
from apps.connectors.slack.ingest import SlackChannelSync, SlackUserSync
from apps.connectors.slack.models import ScbSlackChannel
from apps.data_access.models import Credential, Integration
from apps.identity.models import IdentityType, Person, PersonIdentity


@contextmanager
def _tenant():
    with schema_context("test_tenant"):
        yield


@pytest.fixture
def integration(db) -> Integration:
    with _tenant():
        integ = Integration.objects.create(provider="slack", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"bot_token": "xoxb-fake-token"})
        cred.save()
    return integ


@pytest.mark.django_db
def test_user_sync_creates_person_and_slack_identity(integration: Integration) -> None:
    sample = [
        {"id": "U001", "name": "petr",
         "profile": {"email": "petr@scaleupboard.com", "real_name": "Petr Tománek"},
         "is_bot": False, "deleted": False},
        {"id": "U002", "is_bot": True, "profile": {}, "name": "slackbot"},
    ]
    with _tenant(), patch("apps.connectors.slack.ingest.SlackClient") as MockClient:
        MockClient.return_value.__enter__.return_value.list_users.return_value = sample
        outcome = SlackUserSync(integration).run()

    assert outcome.status == SyncStatus.COMPLETED
    assert outcome.created + outcome.updated == 1  # bot skipped
    assert outcome.skipped == 1
    assert Person.objects.filter(primary_email="petr@scaleupboard.com").exists()
    assert PersonIdentity.objects.filter(
        identity_type=IdentityType.SLACK_ID, identity_value="U001"
    ).exists()


@pytest.mark.django_db
def test_channel_sync_creates_mirror_with_workspace(integration: Integration) -> None:
    team_info = {"id": "T01", "name": "Scaleupboard", "domain": "scaleupboard"}
    channels = [
        {"id": "C001", "name": "sales",
         "purpose": {"value": "Sales team channel"},
         "topic": {"value": ""},
         "is_private": False, "is_archived": False, "num_members": 8},
    ]
    with _tenant(), patch("apps.connectors.slack.ingest.SlackClient") as MockClient:
        mock_ctx = MockClient.return_value.__enter__.return_value
        mock_ctx.team_info.return_value = team_info
        mock_ctx.list_joined_channels.return_value = channels
        outcome = SlackChannelSync(integration).run()

    assert outcome.status == SyncStatus.COMPLETED
    with _tenant():
        ch = ScbSlackChannel.objects.get(slack_channel_id="C001")
        assert ch.name == "sales"
        assert ch.member_count == 8
        assert ch.workspace.team_id == "T01"
