"""Workspace knowledge ingestion: discovery → extraction → chunking → embedding → search.

Public entry points:
    - tasks.full_ingest_workspace        — initial bulk index of every Drive file
    - tasks.incremental_ingest_workspace — Drive Changes API delta sync
    - search.search_chunks               — semantic top-K retrieval
"""

from __future__ import annotations
