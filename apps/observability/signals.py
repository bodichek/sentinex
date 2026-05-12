"""Custom signals raised by alerting tasks."""

from __future__ import annotations

import django.dispatch

high_error_rate = django.dispatch.Signal()
