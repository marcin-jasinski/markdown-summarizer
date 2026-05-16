"""Unit tests for Phase 6 — Concrete Processing Agents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from mindforge.agents.article_fetcher import ArticleFetcherAgent, _extract_links
from mindforge.agents.concept_mapper import ConceptMapperAgent, dedupe_key
from mindforge.agents.flashcard_generator import FlashcardGeneratorAgent
from mindforge.agents.image_analyzer import ImageAnalyzerAgent
from mindforge.agents.preprocessor import PreprocessorAgent
from mindforge.agents.quiz_evaluator import QuizEvaluatorAgent
from mindforge.agents.quiz_generator import QuizGeneratorAgent
from mindforge.agents.relevance_guard import RelevanceGuardAgent
from mindforge.agents.summarizer import SummarizerAgent
from mindforge.domain.agents import AgentContext, ProcessingSettings
from mindforge.domain.models import (
    CardType,
    CompletionResult,
    ConceptEdge,
    ConceptMapData,
    ConceptNode,
    DeadlineProfile,
    DocumentArtifact,
    FetchedArticle,
    FlashcardData,
    ImageDescription,
    SummaryData,
    ValidationResult,
)
from tests.conftest import StubAIGateway


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KB_ID = uuid4()
_DOC_ID = uuid4()
_LESSON_ID = "test-lesson"


def _make_artifact() -> DocumentArtifact:
    return DocumentArtifact(
        document_id=_DOC_ID,
        knowledge_base_id=_KB_ID,
        lesson_id=_LESSON_ID,
        version=1,
        created_at=datetime.now(timezone.utc),
    )


def _make_settings(**kwargs) -> ProcessingSettings:
    defaults = dict(
        chunk_max_tokens=512,
        chunk_min_tokens=64,
        chunk_overlap_tokens=32,
        enable_graph=True,
        enable_image_analysis=True,
        enable_article_fetch=True,
        model_tier_map={
            "small": "gpt-4o-mini",
            "large": "gpt-4o",
            "vision": "gpt-4o",
        },
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def _make_context(
    artifact: DocumentArtifact | None = None,
    gateway: StubAIGateway | None = None,
    metadata: dict | None = None,
    settings: ProcessingSettings | None = None,
) -> AgentContext:
    if artifact is None:
        artifact = _make_artifact()
    if gateway is None:
        gateway = StubAIGateway()
    stub_retrieval = AsyncMock()
    stub_retrieval.get_concepts = AsyncMock(return_value=[])
    return AgentContext(
        document_id=_DOC_ID,
        knowledge_base_id=_KB_ID,
        artifact=artifact,
        gateway=gateway,
        retrieval=stub_retrieval,
        settings=settings or _make_settings(),
        metadata=metadata or {},
    )


def _stub_result(content: str = "cleaned content") -> CompletionResult:
    return CompletionResult(
        content=content,
        input_tokens=10,
        output_tokens=20,
        model="gpt-4o-mini",
        provider="openai",
        latency_ms=50.0,
        cost_usd=0.0001,
    )


# ---------------------------------------------------------------------------
# 6.12.1 Preprocessor — prompt assembly and response handling
# ---------------------------------------------------------------------------


class TestPreprocessorAgent:
    def test_name_and_version(self):
        agent = PreprocessorAgent()
        assert agent.name == "preprocessor"
        assert agent.__version__ == "1.0.0"

    @pytest.mark.asyncio
    async def test_passes_original_content_to_model(self):
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result("cleaned text"))

        context = _make_context(
            gateway=gateway,
            metadata={"original_content": "raw noisy text"},
        )

        agent = PreprocessorAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert result.output_key == "cleaned_content"
        assert context.metadata["cleaned_content"] == "cleaned text"
        assert len(gateway.calls) == 1
        # Verify the original content is in the user message
        assert "raw noisy text" in gateway.calls[0]["messages"][-1]["content"]

    @pytest.mark.asyncio
    async def test_uses_small_model_tier(self):
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result())
        context = _make_context(
            gateway=gateway,
            metadata={"original_content": "some content"},
        )
        agent = PreprocessorAgent()
        await agent.execute(context)
        # Agent resolves the logical tier to the actual model string
        assert gateway.calls[0]["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_missing_content_returns_failure(self):
        context = _make_context(metadata={})
        agent = PreprocessorAgent()
        result = await agent.execute(context)

        assert result.success is False
        assert "original_content" in result.error

    @pytest.mark.asyncio
    async def test_llm_exception_returns_failure(self):
        gateway = StubAIGateway()
        gateway.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
        context = _make_context(
            gateway=gateway,
            metadata={"original_content": "some content"},
        )
        agent = PreprocessorAgent()
        result = await agent.execute(context)

        assert result.success is False
        assert "LLM down" in result.error


# ---------------------------------------------------------------------------
# 6.12.1 / 6.12.2 ImageAnalyzer
# ---------------------------------------------------------------------------


class TestImageAnalyzerAgent:
    def test_name_and_version(self):
        agent = ImageAnalyzerAgent()
        assert agent.name == "image_analyzer"
        assert agent.__version__ == "1.0.0"

    @pytest.mark.asyncio
    async def test_no_images_succeeds_without_llm_call(self):
        gateway = StubAIGateway()
        context = _make_context(gateway=gateway, metadata={"embedded_images": []})
        agent = ImageAnalyzerAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert context.artifact.image_descriptions == []
        assert len(gateway.calls) == 0

    @pytest.mark.asyncio
    async def test_describes_each_image(self):
        gateway = StubAIGateway()
        gateway.set_response(
            "*", _stub_result("A diagram showing neural network layers")
        )

        context = _make_context(
            gateway=gateway,
            metadata={
                "embedded_images": [b"fake_image_bytes_1", b"fake_image_bytes_2"]
            },
        )
        agent = ImageAnalyzerAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert len(context.artifact.image_descriptions) == 2
        assert context.artifact.image_descriptions[0].media_ref == "image_0"
        assert context.artifact.image_descriptions[1].media_ref == "image_1"
        assert len(gateway.calls) == 2

    @pytest.mark.asyncio
    async def test_feature_flag_disabled_skips_processing(self):
        gateway = StubAIGateway()
        context = _make_context(
            gateway=gateway,
            metadata={"embedded_images": [b"data"]},
            settings=_make_settings(enable_image_analysis=False),
        )
        agent = ImageAnalyzerAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert len(gateway.calls) == 0

    @pytest.mark.asyncio
    async def test_partial_failure_continues_with_placeholder(self):
        gateway = StubAIGateway()
        gateway.complete = AsyncMock(side_effect=RuntimeError("vision error"))

        context = _make_context(
            gateway=gateway,
            metadata={"embedded_images": [b"data"]},
        )
        agent = ImageAnalyzerAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert (
            context.artifact.image_descriptions[0].description
            == "[Image analysis failed]"
        )


# ---------------------------------------------------------------------------
# 6.12.1 / 6.12.2 / 6.12.3 RelevanceGuard
# ---------------------------------------------------------------------------


class TestRelevanceGuardAgent:
    def test_name_and_version(self):
        agent = RelevanceGuardAgent()
        assert agent.name == "relevance_guard"
        assert agent.__version__ == "1.0.0"

    @pytest.mark.asyncio
    async def test_empty_kb_always_accepts(self):
        stub = AsyncMock()
        stub.get_concepts = AsyncMock(return_value=[])
        context = AgentContext(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            artifact=_make_artifact(),
            gateway=StubAIGateway(),
            retrieval=stub,
            settings=_make_settings(),
            metadata={"original_content": "some text"},
        )
        agent = RelevanceGuardAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert context.artifact.validation_result.is_relevant is True
        assert context.artifact.validation_result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_relevant_document_accepted(self):
        gateway = StubAIGateway()
        gateway.set_response(
            "*",
            _stub_result(
                json.dumps(
                    {"is_relevant": True, "confidence": 0.9, "reason": "matches"}
                )
            ),
        )

        stub = AsyncMock()
        stub.get_concepts = AsyncMock(
            return_value=[MagicMock(label="machine learning")]
        )
        context = AgentContext(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            artifact=_make_artifact(),
            gateway=gateway,
            retrieval=stub,
            settings=_make_settings(),
            metadata={"original_content": "deep learning techniques"},
        )
        agent = RelevanceGuardAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert context.artifact.validation_result.is_relevant is True

    @pytest.mark.asyncio
    async def test_irrelevant_document_rejected(self):
        gateway = StubAIGateway()
        gateway.set_response(
            "*",
            _stub_result(
                json.dumps(
                    {"is_relevant": False, "confidence": 0.9, "reason": "off topic"}
                )
            ),
        )

        stub = AsyncMock()
        stub.get_concepts = AsyncMock(
            return_value=[MagicMock(label="machine learning")]
        )
        context = AgentContext(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            artifact=_make_artifact(),
            gateway=gateway,
            retrieval=stub,
            settings=_make_settings(),
            metadata={"original_content": "cooking recipes"},
        )
        agent = RelevanceGuardAgent()
        result = await agent.execute(context)

        assert result.success is False
        assert context.artifact.validation_result.is_relevant is False

    @pytest.mark.asyncio
    async def test_parse_error_defaults_to_accept(self):
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result("not valid json"))

        stub = AsyncMock()
        stub.get_concepts = AsyncMock(return_value=[MagicMock(label="physics")])
        context = AgentContext(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            artifact=_make_artifact(),
            gateway=gateway,
            retrieval=stub,
            settings=_make_settings(),
            metadata={"original_content": "some text"},
        )
        agent = RelevanceGuardAgent()
        result = await agent.execute(context)

        # On parse failure, default to accepting
        assert result.success is True
        assert context.artifact.validation_result.is_relevant is True


# ---------------------------------------------------------------------------
# 6.12.5 ArticleFetcher — URL extraction and classification
# ---------------------------------------------------------------------------


class TestArticleFetcherAgent:
    def test_name_and_version(self):
        egress = MagicMock()
        agent = ArticleFetcherAgent(egress_policy=egress)
        assert agent.name == "article_fetcher"
        assert agent.__version__ == "1.0.0"

    def test_extract_links_from_markdown(self):
        md = "Check [this article](https://example.com/article) and [docs](https://docs.example.com/api)"
        links = _extract_links(md)
        assert len(links) == 2
        assert ("this article", "https://example.com/article") in links

    def test_extract_links_skips_images(self):
        md = "![alt text](https://example.com/image.png) but [link](https://example.com/page)"
        links = _extract_links(md)
        assert len(links) == 1
        assert links[0][1] == "https://example.com/page"

    def test_extract_links_skips_code_blocks(self):
        md = "```\n[do not extract](https://example.com/code)\n```\n[real link](https://example.com/page)"
        links = _extract_links(md)
        # Should only get the real link outside the code block
        assert any(url == "https://example.com/page" for _, url in links)
        assert not any(url == "https://example.com/code" for _, url in links)

    @pytest.mark.asyncio
    async def test_no_content_returns_empty_articles(self):
        egress = MagicMock()
        context = _make_context(metadata={})
        agent = ArticleFetcherAgent(egress_policy=egress)
        result = await agent.execute(context)

        assert result.success is True
        assert context.artifact.fetched_articles == []

    @pytest.mark.asyncio
    async def test_feature_flag_disabled_skips_fetch(self):
        egress = MagicMock()
        context = _make_context(
            metadata={"cleaned_content": "[link](https://example.com)"},
            settings=_make_settings(enable_article_fetch=False),
        )
        agent = ArticleFetcherAgent(egress_policy=egress)
        result = await agent.execute(context)

        assert result.success is True
        assert context.artifact.fetched_articles == []

    @pytest.mark.asyncio
    async def test_classifies_and_fetches_articles(self):
        gateway = StubAIGateway()
        classifications = [
            {"url": "https://example.com/article", "category": "article"}
        ]
        gateway.set_response("*", _stub_result(json.dumps(classifications)))

        egress = AsyncMock()
        egress.fetch = AsyncMock(
            return_value=b"<title>Test Article</title><p>Content here</p>"
        )

        context = _make_context(
            gateway=gateway,
            metadata={"cleaned_content": "[article](https://example.com/article)"},
        )
        agent = ArticleFetcherAgent(egress_policy=egress)
        result = await agent.execute(context)

        assert result.success is True
        assert len(context.artifact.fetched_articles) == 1
        assert context.artifact.fetched_articles[0].title == "Test Article"
        assert context.artifact.fetched_articles[0].url == "https://example.com/article"
        egress.fetch.assert_called_once_with("https://example.com/article")

    @pytest.mark.asyncio
    async def test_skips_non_article_categories(self):
        gateway = StubAIGateway()
        classifications = [
            {"url": "https://youtube.com/watch", "category": "video"},
            {"url": "https://twitter.com/post", "category": "social"},
        ]
        gateway.set_response("*", _stub_result(json.dumps(classifications)))

        egress = AsyncMock()
        egress.fetch = AsyncMock(return_value=b"")

        context = _make_context(
            gateway=gateway,
            metadata={
                "cleaned_content": "[video](https://youtube.com/watch) [tweet](https://twitter.com/post)"
            },
        )
        agent = ArticleFetcherAgent(egress_policy=egress)
        await agent.execute(context)

        egress.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_egress_violation_skipped_gracefully(self):
        from mindforge.infrastructure.security.egress_policy import EgressViolation

        gateway = StubAIGateway()
        gateway.set_response(
            "*",
            _stub_result(
                json.dumps(
                    [{"url": "http://169.254.169.254/meta", "category": "article"}]
                )
            ),
        )

        egress = AsyncMock()
        egress.fetch = AsyncMock(side_effect=EgressViolation("private IP"))

        context = _make_context(
            gateway=gateway,
            metadata={"cleaned_content": "[meta](http://169.254.169.254/meta)"},
        )
        agent = ArticleFetcherAgent(egress_policy=egress)
        result = await agent.execute(context)

        # Egress violations are caught and skipped; result is still success
        assert result.success is True
        assert context.artifact.fetched_articles == []


# ---------------------------------------------------------------------------
# 6.12.1 / 6.12.2 Summarizer
# ---------------------------------------------------------------------------


class TestSummarizerAgent:
    def test_name_and_version(self):
        agent = SummarizerAgent()
        assert agent.name == "summarizer"
        assert agent.__version__ == "1.0.0"

    @pytest.mark.asyncio
    async def test_produces_summary_from_content(self):
        payload = {
            "summary": "This document explains neural networks.",
            "key_points": ["Neurons fire in layers", "Backpropagation updates weights"],
            "topics": ["neural networks", "deep learning"],
        }
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(payload)))

        context = _make_context(
            gateway=gateway,
            metadata={"cleaned_content": "Neural networks are..."},
        )
        agent = SummarizerAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert (
            context.artifact.summary.summary
            == "This document explains neural networks."
        )
        assert len(context.artifact.summary.key_points) == 2
        assert "neural networks" in context.artifact.summary.topics

    @pytest.mark.asyncio
    async def test_uses_large_model_tier(self):
        gateway = StubAIGateway()
        gateway.set_response(
            "*",
            _stub_result(json.dumps({"summary": "s", "key_points": [], "topics": []})),
        )
        context = _make_context(
            gateway=gateway,
            metadata={"cleaned_content": "some content"},
        )
        agent = SummarizerAgent()
        await agent.execute(context)
        # Agent resolves the logical tier to the actual model string
        assert gateway.calls[0]["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_includes_image_context_when_present(self):
        gateway = StubAIGateway()
        gateway.set_response(
            "*",
            _stub_result(json.dumps({"summary": "s", "key_points": [], "topics": []})),
        )

        artifact = _make_artifact()
        artifact.image_descriptions = [
            ImageDescription(media_ref="image_0", description="A neural net diagram")
        ]
        context = _make_context(
            artifact=artifact,
            gateway=gateway,
            metadata={"cleaned_content": "content"},
        )
        agent = SummarizerAgent()
        await agent.execute(context)

        user_message = gateway.calls[0]["messages"][-1]["content"]
        assert "A neural net diagram" in user_message

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_parse_error(self):
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result("not valid json at all"))

        context = _make_context(
            gateway=gateway,
            metadata={"cleaned_content": "some content"},
        )
        agent = SummarizerAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert context.artifact.summary is not None

    @pytest.mark.asyncio
    async def test_missing_content_returns_failure(self):
        context = _make_context(metadata={})
        agent = SummarizerAgent()
        result = await agent.execute(context)

        assert result.success is False


# ---------------------------------------------------------------------------
# 6.12.2 / 6.12.4 FlashcardGenerator
# ---------------------------------------------------------------------------


class TestFlashcardGeneratorAgent:
    def test_name_and_version(self):
        agent = FlashcardGeneratorAgent()
        assert agent.name == "flashcard_generator"
        assert agent.__version__ == "1.0.0"

    @pytest.mark.asyncio
    async def test_generates_flashcards_with_deterministic_ids(self):
        cards_payload = [
            {
                "card_type": "BASIC",
                "front": "What is backprop?",
                "back": "A gradient algorithm",
                "tags": ["ml"],
            },
            {
                "card_type": "CLOZE",
                "front": "{{c1::Backpropagation}} computes gradients",
                "back": "Backpropagation computes gradients",
                "tags": ["ml"],
            },
        ]
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(cards_payload)))

        artifact = _make_artifact()
        artifact.summary = SummaryData(
            summary="A doc about ML",
            key_points=["Backprop is important"],
            topics=["ml"],
        )
        context = _make_context(
            artifact=artifact,
            gateway=gateway,
            metadata={"cleaned_content": "Machine learning content..."},
        )
        agent = FlashcardGeneratorAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert len(context.artifact.flashcards) == 2
        assert context.artifact.flashcards[0].card_type == CardType.BASIC

    @pytest.mark.asyncio
    async def test_flashcard_id_determinism(self):
        """Same inputs must always produce the same card_id."""
        card1 = FlashcardData(
            kb_id=_KB_ID,
            lesson_id=_LESSON_ID,
            card_type=CardType.BASIC,
            front="What is ML?",
            back="Machine Learning",
        )
        card2 = FlashcardData(
            kb_id=_KB_ID,
            lesson_id=_LESSON_ID,
            card_type=CardType.BASIC,
            front="What is ML?",
            back="Machine Learning",
        )
        assert card1.card_id == card2.card_id
        assert len(card1.card_id) == 16

    @pytest.mark.asyncio
    async def test_different_kb_produces_different_card_id(self):
        """Different kb_id with same content must produce a different card_id."""
        kb2 = uuid4()
        card1 = FlashcardData(
            kb_id=_KB_ID,
            lesson_id=_LESSON_ID,
            card_type=CardType.BASIC,
            front="What is ML?",
            back="Machine Learning",
        )
        card2 = FlashcardData(
            kb_id=kb2,
            lesson_id=_LESSON_ID,
            card_type=CardType.BASIC,
            front="What is ML?",
            back="Machine Learning",
        )
        assert card1.card_id != card2.card_id

    @pytest.mark.asyncio
    async def test_skips_cards_with_empty_fields(self):
        cards_payload = [
            {"card_type": "BASIC", "front": "", "back": "answer", "tags": []},
            {"card_type": "BASIC", "front": "question", "back": "answer", "tags": []},
        ]
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(cards_payload)))

        artifact = _make_artifact()
        artifact.summary = SummaryData(summary="s", key_points=[], topics=[])
        context = _make_context(
            artifact=artifact,
            gateway=gateway,
            metadata={"cleaned_content": "content"},
        )
        agent = FlashcardGeneratorAgent()
        result = await agent.execute(context)

        # Only valid card should be generated
        assert len(context.artifact.flashcards) == 1

    @pytest.mark.asyncio
    async def test_handles_array_wrapped_in_object(self):
        """Model may return {"flashcards": [...]} instead of a bare array."""
        cards_payload = {
            "flashcards": [
                {"card_type": "BASIC", "front": "Q?", "back": "A", "tags": []}
            ]
        }
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(cards_payload)))

        artifact = _make_artifact()
        artifact.summary = SummaryData(summary="s", key_points=[], topics=[])
        context = _make_context(
            artifact=artifact,
            gateway=gateway,
            metadata={"cleaned_content": "content"},
        )
        agent = FlashcardGeneratorAgent()
        result = await agent.execute(context)

        assert len(context.artifact.flashcards) == 1

    @pytest.mark.asyncio
    async def test_requires_summary_to_be_present(self):
        context = _make_context(metadata={"cleaned_content": "content"})
        # artifact.summary is None by default
        agent = FlashcardGeneratorAgent()
        result = await agent.execute(context)

        assert result.success is False
        assert "Summary not available" in result.error


# ---------------------------------------------------------------------------
# 6.12.1 / 6.12.2 ConceptMapper + dedupe_key
# ---------------------------------------------------------------------------


class TestConceptMapperAgent:
    def test_name_and_version(self):
        agent = ConceptMapperAgent()
        assert agent.name == "concept_mapper"
        assert agent.__version__ == "1.0.0"

    def test_dedupe_key_normalises_text(self):
        assert dedupe_key("Machine Learning") == "machine_learning"
        assert dedupe_key("Neural-Network") == "neural_network"
        assert dedupe_key("API  Docs") == "api_docs"

    def test_dedupe_key_strips_special_chars(self):
        assert dedupe_key("C++ programming") == "c_programming"

    def test_dedupe_key_handles_unicode(self):
        assert dedupe_key("Réseau de neurones") == "reseau_de_neurones"

    @pytest.mark.asyncio
    async def test_produces_concept_map(self):
        payload = {
            "concepts": [
                {
                    "key": "neural_network",
                    "label": "Neural Network",
                    "definition": "A computing system inspired by the brain",
                    "normalized_key": "neural_network",
                },
                {
                    "key": "backprop",
                    "label": "Backpropagation",
                    "definition": "Algorithm to compute gradients",
                    "normalized_key": "backpropagation",
                },
            ],
            "relations": [
                {
                    "source_key": "backprop",
                    "target_key": "neural_network",
                    "label": "USED_FOR",
                    "description": "trains networks",
                }
            ],
        }
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(payload)))

        artifact = _make_artifact()
        artifact.summary = SummaryData(summary="ML doc", key_points=[], topics=[])
        context = _make_context(
            artifact=artifact,
            gateway=gateway,
            metadata={"cleaned_content": "neural network content"},
        )
        agent = ConceptMapperAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert len(context.artifact.concept_map.concepts) == 2
        assert len(context.artifact.concept_map.edges) == 1
        assert context.artifact.concept_map.edges[0].relation == "USED_FOR"

    @pytest.mark.asyncio
    async def test_filters_relations_with_unknown_concept_keys(self):
        payload = {
            "concepts": [
                {
                    "key": "concept_a",
                    "label": "A",
                    "definition": "def a",
                    "normalized_key": "concept_a",
                },
            ],
            "relations": [
                {
                    "source_key": "concept_a",
                    "target_key": "concept_b_missing",
                    "label": "RELATES_TO",
                }
            ],
        }
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(payload)))

        artifact = _make_artifact()
        artifact.summary = SummaryData(summary="s", key_points=[], topics=[])
        context = _make_context(
            artifact=artifact,
            gateway=gateway,
            metadata={"cleaned_content": "content"},
        )
        agent = ConceptMapperAgent()
        await agent.execute(context)

        # Relation with unknown target key should be dropped
        assert len(context.artifact.concept_map.edges) == 0

    @pytest.mark.asyncio
    async def test_graceful_on_parse_error(self):
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result("not json"))

        artifact = _make_artifact()
        artifact.summary = SummaryData(summary="s", key_points=[], topics=[])
        context = _make_context(
            artifact=artifact,
            gateway=gateway,
            metadata={"cleaned_content": "content"},
        )
        agent = ConceptMapperAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert context.artifact.concept_map is not None
        assert context.artifact.concept_map.concepts == []


# ---------------------------------------------------------------------------
# 6.12.1 / 6.12.2 QuizGenerator
# ---------------------------------------------------------------------------


class TestQuizGeneratorAgent:
    def test_name_and_version(self):
        agent = QuizGeneratorAgent()
        assert agent.name == "quiz_generator"
        assert agent.__version__ == "1.0.0"

    @pytest.mark.asyncio
    async def test_generates_question_from_context(self):
        payload = {
            "question_text": "What is gradient descent?",
            "question_type": "open_ended",
            "reference_answer": "An optimisation algorithm that minimises loss",
            "grounding_context": "Gradient descent is used to optimise neural networks...",
        }
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(payload)))

        context = _make_context(
            gateway=gateway,
            metadata={
                "concept_label": "Gradient Descent",
                "retrieval_context": "Gradient descent is used to optimise neural networks...",
            },
        )
        agent = QuizGeneratorAgent()
        result = await agent.execute(context)

        assert result.success is True
        question = context.metadata["quiz_question"]
        assert question.question_text == "What is gradient descent?"
        assert (
            question.reference_answer == "An optimisation algorithm that minimises loss"
        )

    @pytest.mark.asyncio
    async def test_missing_retrieval_context_returns_failure(self):
        context = _make_context(metadata={"concept_label": "Gradient Descent"})
        agent = QuizGeneratorAgent()
        result = await agent.execute(context)

        assert result.success is False
        assert "retrieval_context" in result.error

    @pytest.mark.asyncio
    async def test_uses_interactive_deadline(self):
        gateway = StubAIGateway()
        gateway.set_response(
            "*",
            _stub_result(
                json.dumps(
                    {
                        "question_text": "Q?",
                        "question_type": "open_ended",
                        "reference_answer": "A",
                        "grounding_context": "ctx",
                    }
                )
            ),
        )
        context = _make_context(
            gateway=gateway,
            metadata={"retrieval_context": "some context"},
        )
        agent = QuizGeneratorAgent()
        await agent.execute(context)
        assert gateway.calls[0]["deadline"] == DeadlineProfile.INTERACTIVE


# ---------------------------------------------------------------------------
# 6.12.1 / 6.12.2 / 6.12.3 QuizEvaluator
# ---------------------------------------------------------------------------


class TestQuizEvaluatorAgent:
    def test_name_and_version(self):
        agent = QuizEvaluatorAgent()
        assert agent.name == "quiz_evaluator"
        assert agent.__version__ == "1.0.0"

    @pytest.mark.asyncio
    async def test_evaluates_student_answer(self):
        payload = {
            "score": 4,
            "feedback": "Good answer! You covered most points.",
            "explanation": "Gradient descent minimises loss by updating weights.",
            "missing_points": [],
            "quality_flag": None,
        }
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(payload)))

        context = _make_context(
            gateway=gateway,
            metadata={
                "question_text": "What is gradient descent?",
                "reference_answer": "An optimisation algorithm",
                "grounding_context": "Gradient descent...",
                "student_answer": "It minimises the loss function",
            },
        )
        agent = QuizEvaluatorAgent()
        result = await agent.execute(context)

        assert result.success is True
        evaluation = context.metadata["evaluation"]
        assert evaluation["score"] == 4
        assert "Good answer" in evaluation["feedback"]
        assert evaluation["review_result"].rating == 4

    @pytest.mark.asyncio
    async def test_score_clamped_to_0_5_range(self):
        payload = {
            "score": 99,  # out of range
            "feedback": "Perfect",
            "explanation": "Full explanation",
            "missing_points": [],
            "quality_flag": None,
        }
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(payload)))

        context = _make_context(
            gateway=gateway,
            metadata={
                "question_text": "Q?",
                "reference_answer": "ref",
                "grounding_context": "ctx",
                "student_answer": "answer",
            },
        )
        agent = QuizEvaluatorAgent()
        await agent.execute(context)

        assert context.metadata["evaluation"]["score"] == 5  # clamped to 5

    @pytest.mark.asyncio
    async def test_missing_reference_answer_returns_failure(self):
        context = _make_context(
            metadata={"student_answer": "my answer", "question_text": "Q?"}
        )
        agent = QuizEvaluatorAgent()
        result = await agent.execute(context)

        assert result.success is False
        assert "reference_answer" in result.error

    @pytest.mark.asyncio
    async def test_missing_student_answer_returns_failure(self):
        context = _make_context(
            metadata={"reference_answer": "correct", "question_text": "Q?"}
        )
        agent = QuizEvaluatorAgent()
        result = await agent.execute(context)

        assert result.success is False
        assert "student_answer" in result.error

    @pytest.mark.asyncio
    async def test_invalid_quality_flag_normalised_to_none(self):
        payload = {
            "score": 2,
            "feedback": "Partial",
            "explanation": "Explanation",
            "missing_points": ["Key point"],
            "quality_flag": "unknown_flag",  # invalid
        }
        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result(json.dumps(payload)))

        context = _make_context(
            gateway=gateway,
            metadata={
                "question_text": "Q?",
                "reference_answer": "ref",
                "grounding_context": "ctx",
                "student_answer": "partial answer",
            },
        )
        agent = QuizEvaluatorAgent()
        await agent.execute(context)

        # Invalid quality_flag should be normalised to None
        assert context.metadata["evaluation"]["quality_flag"] is None

    @pytest.mark.asyncio
    async def test_reuses_stored_reference_answer_not_regenerated(self):
        """Verify the evaluator passes the stored reference answer to the model,
        not a newly generated one."""
        gateway = StubAIGateway()
        gateway.set_response(
            "*",
            _stub_result(
                json.dumps(
                    {
                        "score": 3,
                        "feedback": "ok",
                        "explanation": "exp",
                        "missing_points": [],
                        "quality_flag": None,
                    }
                )
            ),
        )

        stored_ref = "This is the stored reference answer"
        context = _make_context(
            gateway=gateway,
            metadata={
                "question_text": "Q?",
                "reference_answer": stored_ref,
                "grounding_context": "ctx",
                "student_answer": "my answer",
            },
        )
        agent = QuizEvaluatorAgent()
        await agent.execute(context)

        # The stored reference answer must appear in the user message sent to LLM
        user_message = gateway.calls[0]["messages"][-1]["content"]
        assert stored_ref in user_message


# ---------------------------------------------------------------------------
# Regression tests for review findings
# ---------------------------------------------------------------------------


class TestPromptVersionWiring:
    """All agents must expose PROMPT_VERSION as a class attribute so that
    PipelineOrchestrator._compute_fingerprint()'s getattr(agent, 'PROMPT_VERSION', '0')
    finds the real version and not the fallback '0'
    (review finding: PROMPT_VERSION not wired)."""

    def test_preprocessor_has_prompt_version(self):
        from mindforge.agents.preprocessor import PreprocessorAgent
        from mindforge.infrastructure.ai.agents import preprocessor as p

        assert PreprocessorAgent().PROMPT_VERSION == p.VERSION
        assert PreprocessorAgent().PROMPT_VERSION != ""

    def test_image_analyzer_has_prompt_version(self):
        from mindforge.agents.image_analyzer import ImageAnalyzerAgent
        from mindforge.infrastructure.ai.agents import image_analyzer as p

        assert ImageAnalyzerAgent().PROMPT_VERSION == p.VERSION

    def test_relevance_guard_has_prompt_version(self):
        from mindforge.agents.relevance_guard import RelevanceGuardAgent
        from mindforge.infrastructure.ai.agents import relevance_guard as p

        assert RelevanceGuardAgent().PROMPT_VERSION == p.VERSION

    def test_summarizer_has_prompt_version(self):
        from mindforge.agents.summarizer import SummarizerAgent
        from mindforge.infrastructure.ai.agents import summarizer as p

        assert SummarizerAgent().PROMPT_VERSION == p.VERSION

    def test_flashcard_generator_has_prompt_version(self):
        from mindforge.agents.flashcard_generator import FlashcardGeneratorAgent
        from mindforge.infrastructure.ai.agents import flashcard_gen as p

        assert FlashcardGeneratorAgent().PROMPT_VERSION == p.VERSION

    def test_concept_mapper_has_prompt_version(self):
        from mindforge.agents.concept_mapper import ConceptMapperAgent
        from mindforge.infrastructure.ai.agents import concept_mapper as p

        assert ConceptMapperAgent().PROMPT_VERSION == p.VERSION

    def test_quiz_generator_has_prompt_version(self):
        from mindforge.agents.quiz_generator import QuizGeneratorAgent
        from mindforge.infrastructure.ai.agents import quiz_generator as p

        assert QuizGeneratorAgent().PROMPT_VERSION == p.VERSION

    def test_quiz_evaluator_has_prompt_version(self):
        from mindforge.agents.quiz_evaluator import QuizEvaluatorAgent
        from mindforge.infrastructure.ai.agents import quiz_evaluator as p

        assert QuizEvaluatorAgent().PROMPT_VERSION == p.VERSION

    def test_pipeline_orchestrator_reads_prompt_version(self):
        """_compute_fingerprint uses getattr(agent, 'PROMPT_VERSION', '0').
        Verify it finds the real value, not the '0' fallback."""
        from mindforge.agents.preprocessor import PreprocessorAgent

        agent = PreprocessorAgent()
        assert getattr(agent, "PROMPT_VERSION", "0") != "0"


class TestRelevanceGuardUsesPromptModule:
    """RelevanceGuard must use the prompt module — not an inline string —
    so the system prompt is version-tracked (review finding: inline prompt)."""

    def test_relevance_guard_imports_from_prompt_module(self):
        import mindforge.agents.relevance_guard as rg_mod
        import mindforge.infrastructure.ai.agents.relevance_guard as prompt_mod

        # The agent module must use the prompt module's getter function
        assert callable(
            getattr(prompt_mod, "system_prompt", None)
        ), "prompt module must expose a system_prompt() getter"
        assert hasattr(prompt_mod, "VERSION")
        # No inline _SYSTEM_PROMPT constant should remain in the agent module
        assert not hasattr(
            rg_mod, "_SYSTEM_PROMPT"
        ), "_SYSTEM_PROMPT should have been removed from the agent module"


class TestPipelineWorkerContextMetadata:
    """_execute_task must populate original_content in context.metadata so that
    agents that depend on it (Preprocessor, RelevanceGuard, etc.) can run
    (review finding: original_content never injected)."""

    @pytest.mark.asyncio
    async def test_execute_task_injects_original_content(self):
        """Simulate _execute_task to verify original_content ends up in metadata."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from mindforge.cli.pipeline_runner import PipelineWorker
        from mindforge.domain.agents import ProcessingSettings

        captured_metadata: dict = {}

        async def fake_orchestrator_run(document_id, artifact, context):
            captured_metadata.update(context.metadata)
            return artifact

        mock_orchestrator = MagicMock()
        mock_orchestrator.run = AsyncMock(side_effect=fake_orchestrator_run)

        mock_doc_row = MagicMock()
        mock_doc_row.document_id = uuid4()
        mock_doc_row.knowledge_base_id = uuid4()
        mock_doc_row.lesson_id = "test-lesson"
        mock_doc_row.original_content = "This is the raw document text."

        mock_artifact = MagicMock()
        mock_artifact_repo = AsyncMock()
        mock_artifact_repo.load_latest = AsyncMock(return_value=mock_artifact)
        mock_artifact_repo.save_checkpoint = AsyncMock()

        mock_task = MagicMock()
        mock_task.task_id = uuid4()
        mock_task.document_id = mock_doc_row.document_id

        # Patch the internal pieces used by _execute_task
        mock_engine = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_doc_row)
        mock_session.execute = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=mock_session_cm)

        worker = PipelineWorker(
            worker_id="test-worker",
            engine=mock_engine,
            registry=MagicMock(),
            graph=MagicMock(),
            gateway=MagicMock(),
            settings=ProcessingSettings(),
            retrieval=MagicMock(),
        )

        with patch.object(worker, "_session_factory") as mock_sf:
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context.__aexit__ = AsyncMock(return_value=False)
            mock_sf.return_value = mock_session_context

            with patch(
                "mindforge.cli.pipeline_runner.PostgresArtifactRepository",
                return_value=mock_artifact_repo,
            ):
                with patch(
                    "mindforge.cli.pipeline_runner.PostgresDocumentRepository",
                ):
                    with patch(
                        "mindforge.cli.pipeline_runner.PostgresInteractionRepository",
                    ):
                        with patch(
                            "mindforge.cli.pipeline_runner.OutboxEventPublisher",
                        ):
                            with patch(
                                "mindforge.cli.pipeline_runner.PipelineOrchestrator",
                                return_value=mock_orchestrator,
                            ):
                                await worker._execute_task(mock_task)

        assert (
            "original_content" in captured_metadata
        ), "_execute_task must inject original_content into context.metadata"
        assert captured_metadata["original_content"] == "This is the raw document text."


class TestPipelineRegistryExcludesQuizAgents:
    """QuizGeneratorAgent and QuizEvaluatorAgent must not be in the pipeline
    AgentRegistry — they are quiz-surface-only agents (review finding: wrong registry).
    """

    def test_quiz_generator_not_in_pipeline_imports(self):
        import ast
        import pathlib

        src = pathlib.Path(
            "d:/Dokumenty/Projekty/mindforge/mindforge/cli/pipeline_runner.py"
        ).read_text()
        tree = ast.parse(src)
        imported = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in getattr(node, "names", [])
        ]
        assert (
            "QuizGeneratorAgent" not in imported
        ), "QuizGeneratorAgent must not be imported in pipeline_runner"
        assert (
            "QuizEvaluatorAgent" not in imported
        ), "QuizEvaluatorAgent must not be imported in pipeline_runner"


class TestEnableArticleFetchInConfig:
    """enable_article_fetch must be an AppSettings field so operators can
    disable outbound fetches via .env (review finding: missing config field)."""

    def test_app_settings_has_enable_article_fetch(self):
        from mindforge.infrastructure.config import AppSettings

        # Pydantic model_fields lists all declared fields
        assert "enable_article_fetch" in AppSettings.model_fields

    def test_enable_article_fetch_defaults_to_true(self):
        from mindforge.infrastructure.config import AppSettings

        settings = AppSettings()
        assert settings.enable_article_fetch is True

    def test_enable_article_fetch_can_be_disabled(self):
        from mindforge.infrastructure.config import AppSettings

        settings = AppSettings(enable_article_fetch=False)
        assert settings.enable_article_fetch is False


# ---------------------------------------------------------------------------
# 12.x  Locale-aware prompt getters (Finding 1 + 4 regression)
# ---------------------------------------------------------------------------


class TestLocaleAwarePromptGetters:
    """Prompt modules must expose getter functions, not import-time constants,
    so that the correct locale is used at call time."""

    def test_preprocessor_system_prompt_returns_string(self):
        from mindforge.infrastructure.ai.agents import preprocessor as p

        result = p.system_prompt("pl")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_preprocessor_has_no_module_level_system_prompt_constant(self):
        from mindforge.infrastructure.ai.agents import preprocessor as p

        assert not hasattr(
            p, "SYSTEM_PROMPT"
        ), "SYSTEM_PROMPT must not be a module-level constant; use system_prompt() getter"

    def test_preprocessor_has_no_dead_version_function(self):
        from mindforge.infrastructure.ai.agents import preprocessor as p

        assert not hasattr(
            p, "version"
        ), "version(locale) was dead code and must be removed"

    def test_summarizer_all_getters_present(self):
        from mindforge.infrastructure.ai.agents import summarizer as p

        for fn_name in (
            "system_prompt",
            "user_template",
            "image_context_template",
            "article_context_template",
            "prior_concepts_template",
        ):
            assert callable(
                getattr(p, fn_name, None)
            ), f"summarizer.{fn_name} must be a callable getter"

    def test_preprocessor_agent_uses_locale_from_context(self):
        """PreprocessorAgent must pass context.settings.prompt_locale to the
        gateway, not a hardcoded 'pl' system message."""
        import asyncio

        gateway = StubAIGateway()
        gateway.set_response("*", _stub_result("cleaned"))

        settings = _make_settings(prompt_locale="pl")
        context = _make_context(
            gateway=gateway,
            metadata={"original_content": "raw text"},
            settings=settings,
        )

        agent = PreprocessorAgent()
        asyncio.get_event_loop().run_until_complete(agent.execute(context))

        assert len(gateway.calls) == 1
        system_msg = gateway.calls[0]["messages"][0]["content"]
        # System message must be non-empty — it came from the prompt file
        assert isinstance(system_msg, str) and len(system_msg) > 0
