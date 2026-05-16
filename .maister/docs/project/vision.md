# Project Vision

## Overview

MindForge is an AI-powered learning platform that transforms uploaded documents into
structured study artifacts and provides interactive knowledge assessment. A user uploads
a document (Markdown, PDF, DOCX, or TXT), the system extracts and enriches the content,
generates summaries, flashcards, and concept maps, builds a queryable knowledge graph,
and then exposes this knowledge through a web UI, an interactive quiz engine, and a Discord bot.

## Current State

- **Version**: 2.0.0
- **Status**: Active development — phases 0–12 of 19 completed (core pipeline + API + frontend done)
- **Users**: Solo developer / personal learning tool
- **Tech Stack**: Python 3.12 / FastAPI / Angular 21 / PostgreSQL / Neo4j / LiteLLM

## Purpose

MindForge exists to solve the personal learning problem: raw learning materials are
hard to internalize. The system automates the conversion of any document into study
artifacts (summaries, flashcards, concept maps) and provides active recall through
quizzes — all driven by AI so the learner focuses on learning, not on note-taking.

**Core value loop:**
1. Upload any document → 2. AI pipeline generates artifacts → 3. Study via quizzes & concept maps → 4. Track retention over time

## Goals (Next 6–12 Months)

### Short-term (Phases 13–16)
- Complete Discord and Slack bot integrations for ambient learning
- Finalize all CLI entry points for scripted workflows
- Full observability and tracing coverage with Langfuse dashboards

### Medium-term (Phases 17–19)
- Docker + Docker Compose for reproducible local and cloud deployment
- Security hardening pass (penetration testing, regression suite)
- End-to-end test suite and quality gates (≥80% coverage, CI/CD pipeline)

### Long-term
- English locale prompt support alongside existing Polish
- Multi-worker Redis-backed rate limiting
- CI/CD automation (GitHub Actions) for lint, type-check, and test gates on every PR
- Mobile-friendly responsive frontend improvements

## Evolution

MindForge 2.0 is a greenfield rewrite guided by hexagonal architecture principles.
The core product (document ingestion pipeline, quiz engine, knowledge graph, Angular SPA)
is feature-complete. The remaining phases focus on deployment hardening, multi-channel
integrations (Discord, Slack), and quality assurance.

The architecture is intentionally designed to support new document formats, AI agent types,
and runtime surfaces (new chat platforms) without modifying the core orchestrator — enabling
incremental expansion while keeping the domain layer stable.

---
*Last Updated*: 2026-04-22
*Project Reference*: [architecture.md](../../../.github/docs/architecture.md) | [implementation-plan.md](../../../.github/docs/implementation-plan.md)
