"""Unit tests for AnswerGenerator lazy initialization."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evaluation.answer_generator import AnswerGenerator


class TestAnswerGenerator:
    """Test suite for AnswerGenerator."""

    def test_init_without_agent_does_not_initialize(self):
        """Verify AnswerGenerator can be instantiated without triggering agent creation."""
        generator = AnswerGenerator(
            input_file=Path("dummy_input.xlsx"), output_file=Path("dummy_output.csv")
        )
        assert generator.agent is None

    @pytest.mark.asyncio
    async def test_get_agent_initializes_lazily(self):
        """Verify get_agent lazily instantiates the agent via factory."""
        generator = AnswerGenerator(
            input_file=Path("dummy_input.xlsx"), output_file=Path("dummy_output.csv")
        )

        mock_agent = MagicMock()
        with patch(
            "evaluation.answer_generator.create_rag_agent_instance",
            new_callable=AsyncMock,
        ) as mock_factory:
            mock_factory.return_value = mock_agent
            agent = await generator.get_agent()
            assert agent is mock_agent
            assert generator.agent is mock_agent
            mock_factory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_answer_for_question_calls_agent(self):
        """Verify generate_answer_for_question invokes agent and formats result."""
        mock_agent = MagicMock()
        mock_response = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "Employees get 25 days leave."
        mock_response = {"messages": [mock_msg]}
        mock_agent.ainvoke = AsyncMock(return_value=mock_response)

        generator = AnswerGenerator(
            input_file=Path("dummy_input.xlsx"),
            output_file=Path("dummy_output.csv"),
            agent=mock_agent,
        )

        result = await generator.generate_answer_for_question("How many days leave?")
        assert result["answer"] == "Employees get 25 days leave."
        assert result["error"] is None
        mock_agent.ainvoke.assert_awaited_once()
