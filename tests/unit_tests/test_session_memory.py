"""Unit tests for Phase 5: Persistent Conversation Memory."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from pymongo.errors import ServerSelectionTimeoutError

from evaluation.answer_generator import AnswerGenerator
from mcp_rag_agent.agent.create_agent import create_rag_agent_instance
from mcp_rag_agent.agent.models import AgentResponse
from mcp_rag_agent.agent.runner import RAGAgentRunner
from mcp_rag_agent.core.checkpointer import get_checkpointer, get_checkpointer_async
from mcp_rag_agent.core.config import Config


class TestSessionMemoryCheckpointer:
    """Test suite for core/checkpointer.py factory and fallback logic."""

    def test_feature_flag_disabled_returns_none(self):
        """When FEATURE_FLAG_SESSION_MEMORY_ENABLED=false, get_checkpointer returns None."""
        cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_db",
            model_api_key="sk-test",
            ff_session_memory=False,
        )
        checkpointer = get_checkpointer(cfg)
        assert checkpointer is None

    def test_missing_database_url_degrades_to_memory(self):
        """When db_url or db_name is empty, degrades gracefully to MemorySaver."""
        cfg = Config(
            db_url="",
            db_name="",
            model_api_key="sk-test",
            ff_session_memory=True,
        )
        checkpointer = get_checkpointer(cfg, fallback_on_error=True)
        assert isinstance(checkpointer, MemorySaver)

    def test_missing_database_url_returns_none_if_no_fallback(self):
        """When fallback_on_error=False, returns None if configuration is missing."""
        cfg = Config(
            db_url="",
            db_name="",
            model_api_key="sk-test",
            ff_session_memory=True,
        )
        checkpointer = get_checkpointer(cfg, fallback_on_error=False)
        assert checkpointer is None

    def test_checkpointer_initialization_with_mongodb(self):
        """When MongoDB connection succeeds, initializes MongoDBSaver with configured collections."""
        cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_db",
            db_checkpoints_collection="custom_checkpoints",
            db_checkpoint_writes_collection="custom_writes",
            model_api_key="sk-test",
            ff_session_memory=True,
            session_memory_ttl_seconds=3600,
        )

        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}

        with patch(
            "mcp_rag_agent.core.checkpointer.MongoClient", return_value=mock_client
        ):
            with patch(
                "mcp_rag_agent.core.checkpointer.MongoDBSaver"
            ) as mock_saver_cls:
                mock_saver_instance = MagicMock()
                mock_saver_cls.return_value = mock_saver_instance

                checkpointer = get_checkpointer(cfg)
                assert checkpointer is mock_saver_instance
                mock_client.admin.command.assert_called_with("ping")
                mock_saver_cls.assert_called_once_with(
                    client=mock_client,
                    db_name="test_db",
                    checkpoint_collection_name="custom_checkpoints",
                    writes_collection_name="custom_writes",
                    ttl=3600,
                )

    def test_connection_failure_gracefully_degrades_to_memory(self):
        """When MongoDB ping times out or fails, catches exception and degrades to MemorySaver."""
        cfg = Config(
            db_url="mongodb+srv://user:secretpassword@test.cluster.mongodb.net",
            db_name="test_db",
            model_api_key="sk-test",
            ff_session_memory=True,
        )

        mock_client = MagicMock()
        mock_client.admin.command.side_effect = ServerSelectionTimeoutError(
            "Server unreachable on port 27017"
        )

        with patch(
            "mcp_rag_agent.core.checkpointer.MongoClient", return_value=mock_client
        ):
            with patch("mcp_rag_agent.core.checkpointer.logger") as mock_logger:
                checkpointer = get_checkpointer(cfg, fallback_on_error=True)
                assert isinstance(checkpointer, MemorySaver)
                # Verify logger was called with warning
                mock_logger.warning.assert_called_once()
                warning_message = mock_logger.warning.call_args[0][0]
                assert "MongoDB connection failed" in warning_message
                # Verify secret password was not leaked
                assert "secretpassword" not in warning_message

    @pytest.mark.asyncio
    async def test_get_checkpointer_async_wrapper(self):
        """Verify get_checkpointer_async executes asynchronously without blocking."""
        cfg = Config(
            db_url="",
            db_name="",
            model_api_key="sk-test",
            ff_session_memory=True,
        )
        checkpointer = await get_checkpointer_async(cfg)
        assert isinstance(checkpointer, MemorySaver)


class TestThreadIsolationAndPersistence:
    """Test suite for thread isolation and multi-turn state persistence."""

    @pytest.mark.asyncio
    async def test_thread_isolation(self):
        """Ensure turn on thread_A does not leak into thread_B."""
        mock_graph = MagicMock()
        invocations = []

        async def fake_ainvoke(input_data, config=None):
            cfg = config or {}
            thread_id = cfg.get("configurable", {}).get("thread_id", "default")
            invocations.append((thread_id, input_data["messages"][-1].content))
            msg = MagicMock()
            msg.content = f"Response for {thread_id}"
            return {"messages": [msg]}

        mock_graph.ainvoke = AsyncMock(side_effect=fake_ainvoke)
        runner = RAGAgentRunner(agent_graph=mock_graph, checkpointer=MemorySaver())

        # Turn 1 on thread_A
        res_a = await runner.run(
            "Hello from Thread A", thread_id="thread_A", user_id="user_1"
        )
        assert res_a.metadata.thread_id == "thread_A"
        assert res_a.metadata.user_id == "user_1"

        # Turn 1 on thread_B
        res_b = await runner.run(
            "Hello from Thread B", thread_id="thread_B", user_id="user_2"
        )
        assert res_b.metadata.thread_id == "thread_B"
        assert res_b.metadata.user_id == "user_2"

        # Verify invocations carried isolated thread_ids
        assert invocations[0] == ("thread_A", "Hello from Thread A")
        assert invocations[1] == ("thread_B", "Hello from Thread B")

    @pytest.mark.asyncio
    async def test_conversation_persistence_across_instances(self):
        """Simulate process restart: state saved on thread_id is available to a new instance."""
        shared_memory_saver = MemorySaver()

        # Mock agent graph that preserves message history via checkpointer
        state_store = {}

        def make_agent_graph():
            graph = MagicMock()

            async def fake_ainvoke(input_data, config=None):
                th = config.get("configurable", {}).get("thread_id", "default")
                history = state_store.setdefault(th, [])
                new_msg = input_data["messages"][-1].content
                history.append(f"User: {new_msg}")
                reply = MagicMock()
                reply.content = f"History size is {len(history)}."
                return {"messages": [reply]}

            graph.ainvoke = AsyncMock(side_effect=fake_ainvoke)
            return graph

        # Instance 1 (Pre-restart)
        runner1 = RAGAgentRunner(
            agent_graph=make_agent_graph(), checkpointer=shared_memory_saver
        )
        res1 = await runner1.run(
            "First question about leave", thread_id="session_persist"
        )
        assert "History size is 1" in res1.answer

        # Instance 2 (Post-restart, separate runner with same shared checkpointer)
        runner2 = RAGAgentRunner(
            agent_graph=make_agent_graph(), checkpointer=shared_memory_saver
        )
        res2 = await runner2.run(
            "Follow-up question about carryover", thread_id="session_persist"
        )
        assert "History size is 2" in res2.answer

    @pytest.mark.asyncio
    async def test_direct_mode_agent_creation_wires_checkpointer(self):
        """Verify Direct mode agent receives checkpointer."""
        cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_db",
            model_api_key="sk-test",
            ff_mcp_server=False,
            ff_session_memory=False,  # Test explicit checkpointer injection
        )
        custom_checkpointer = MemorySaver()

        with patch(
            "mcp_rag_agent.agent.create_agent.create_rag_agent", new_callable=AsyncMock
        ) as mock_direct_create:
            mock_direct_create.return_value = MagicMock()

            runner = await create_rag_agent_instance(
                cfg=cfg, checkpointer=custom_checkpointer
            )
            assert runner.checkpointer is custom_checkpointer
            mock_direct_create.assert_awaited_once()
            # Verify checkpointer was passed to create_rag_agent
            assert (
                mock_direct_create.call_args[1]["checkpointer"] is custom_checkpointer
            )

    @pytest.mark.asyncio
    async def test_mcp_mode_agent_creation_wires_checkpointer(self):
        """Verify MCP mode agent receives checkpointer."""
        cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_db",
            model_api_key="sk-test",
            ff_mcp_server=True,
            ff_session_memory=False,
        )
        custom_checkpointer = MemorySaver()

        with patch(
            "mcp_rag_agent.agent.create_agent.create_mcp_rag_agent",
            new_callable=AsyncMock,
        ) as mock_mcp_create:
            mock_mcp_create.return_value = MagicMock()

            runner = await create_rag_agent_instance(
                cfg=cfg, checkpointer=custom_checkpointer
            )
            assert runner.checkpointer is custom_checkpointer
            mock_mcp_create.assert_awaited_once()
            # Verify checkpointer was passed to create_mcp_rag_agent
            assert mock_mcp_create.call_args[1]["checkpointer"] is custom_checkpointer

    @pytest.mark.asyncio
    async def test_evaluation_questions_receive_isolated_threads(self):
        """Verify evaluation answer generator passes a distinct thread ID for every question."""
        recorded_threads = []

        mock_agent = MagicMock()

        async def capture_ainvoke(input_data, config=None, **kwargs):
            cfg = config or {}
            th = input_data.get("thread_id") or cfg.get("configurable", {}).get(
                "thread_id"
            )
            recorded_threads.append(th)
            msg = MagicMock()
            msg.content = "Evaluation answer"
            return {"messages": [msg]}

        mock_agent.ainvoke = AsyncMock(side_effect=capture_ainvoke)

        generator = AnswerGenerator(
            input_file=Path("dummy_input.xlsx"),
            output_file=Path("dummy_output.csv"),
            agent=mock_agent,
        )

        await generator.generate_answer_for_question("Question 1: Remote work policy?")
        await generator.generate_answer_for_question(
            "Question 2: Annual leave carryover?"
        )
        await generator.generate_answer_for_question("Question 3: Expense receipts?")

        assert len(recorded_threads) == 3
        # Ensure all thread IDs are non-null and strictly unique
        assert all(t is not None for t in recorded_threads)
        assert len(set(recorded_threads)) == 3
        # Ensure thread IDs follow evaluation naming convention
        assert all(t.startswith("eval_") for t in recorded_threads)

    def test_no_import_time_side_effects(self):
        """Ensure checkpointer module import causes no network calls or event loop side effects."""
        import mcp_rag_agent.core.checkpointer as cp_module

        assert hasattr(cp_module, "get_checkpointer")
        assert hasattr(cp_module, "get_checkpointer_async")
