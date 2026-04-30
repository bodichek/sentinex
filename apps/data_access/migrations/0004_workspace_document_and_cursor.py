"""WorkspaceDocument + IngestionCursor + DWD provider choice."""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_access", "0003_alter_integration_provider"),
    ]

    operations = [
        migrations.AlterField(
            model_name="integration",
            name="provider",
            field=models.CharField(
                choices=[
                    ("google_workspace", "Google Workspace (per-user OAuth)"),
                    ("google_workspace_dwd", "Google Workspace (Domain-Wide Delegation)"),
                    ("slack", "Slack"),
                ],
                max_length=40,
            ),
        ),
        migrations.CreateModel(
            name="WorkspaceDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("drive", "Drive"),
                            ("gmail", "Gmail"),
                            ("calendar", "Calendar"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("external_id", models.CharField(db_index=True, max_length=255)),
                ("title", models.CharField(blank=True, max_length=512)),
                ("mime_type", models.CharField(blank=True, max_length=128)),
                ("owner_email", models.EmailField(blank=True, max_length=254)),
                ("web_view_link", models.URLField(blank=True, max_length=1024)),
                ("modified_at", models.DateTimeField(blank=True, null=True)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("text_content", models.TextField(blank=True)),
                ("text_truncated", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("extracted", "Extracted"),
                            ("indexed", "Indexed"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error", models.CharField(blank=True, max_length=500)),
                ("extracted_at", models.DateTimeField(blank=True, null=True)),
                ("indexed_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["source", "status"], name="data_access_doc_src_st_idx"),
                    models.Index(fields=["owner_email"], name="data_access_doc_owner_idx"),
                    models.Index(fields=["-modified_at"], name="data_access_doc_mod_idx"),
                ],
                "unique_together": {("source", "external_id")},
            },
        ),
        migrations.CreateModel(
            name="IngestionCursor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("source", models.CharField(max_length=40, unique=True)),
                ("cursor", models.CharField(blank=True, max_length=255)),
                ("last_full_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_incremental_sync_at", models.DateTimeField(blank=True, null=True)),
                ("files_total", models.IntegerField(default=0)),
                ("files_indexed", models.IntegerField(default=0)),
                ("files_failed", models.IntegerField(default=0)),
            ],
        ),
    ]
