from __future__ import annotations

from django.apps import AppConfig


class MailchimpConnectorConfig(AppConfig):
    name = "apps.connectors.mailchimp"
    label = "connectors_mailchimp"
    verbose_name = "Mailchimp connector"
