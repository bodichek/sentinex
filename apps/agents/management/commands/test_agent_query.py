"""Submit a query to the orchestrator from the CLI."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from django.core.management.base import BaseCommand

from apps.agents import context_builder
from apps.agents.orchestrator import Orchestrator


class Command(BaseCommand):
    help = "Submit a query through the Orchestrator and print the response."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("query", help="User query to send")
        parser.add_argument("--json", action="store_true", help="Print full JSON response")

    def handle(self, *args: Any, **opts: Any) -> None:
        query = opts["query"]
        context = context_builder.build(query)
        response = Orchestrator().handle(query, context)

        if opts["json"]:
            payload = {
                "intent": asdict(response.intent),
                "final": response.final,
                "specialists": [
                    {"name": s.name, "content": s.content} for s in response.specialist_responses
                ],
            }
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.SUCCESS(f"Intent: {response.intent.intent}"))
        self.stdout.write(f"Summary: {response.intent.summary}")
        for s in response.specialist_responses:
            self.stdout.write(self.style.NOTICE(f"\n--- {s.name} ---"))
            self.stdout.write(s.content)
        self.stdout.write(self.style.SUCCESS("\n=== Final ==="))
        self.stdout.write(response.final)
