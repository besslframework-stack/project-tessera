"""Tests for agent framework adapters (Phase 8c)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.adapters import (
    TesseraAutoGenTool,
    TesseraCrewAITool,
    TesseraLangChainRetriever,
    get_adapter,
    get_adapter_info,
)


class TestTesseraLangChainRetriever:
    @patch("src.memory.recall_memories")
    def test_get_relevant_documents(self, mock_recall):
        mock_recall.return_value = [
            {"content": "Use PostgreSQL", "date": "2026-03-15", "category": "fact", "tags": "db", "file_path": "/tmp/m1.md"},
        ]
        retriever = TesseraLangChainRetriever(top_k=3)
        docs = retriever.get_relevant_documents("database")
        assert len(docs) == 1
        assert docs[0]["page_content"] == "Use PostgreSQL"
        assert docs[0]["metadata"]["source"] == "tessera"
        mock_recall.assert_called_once_with("database", top_k=3)

    @patch("src.memory.recall_memories", return_value=[])
    def test_empty_results(self, mock_recall):
        retriever = TesseraLangChainRetriever()
        docs = retriever.get_relevant_documents("nothing")
        assert docs == []

    @patch("src.memory.recall_memories", return_value=[{"content": "test", "date": "", "category": "", "tags": "", "file_path": ""}])
    def test_invoke_alias(self, mock_recall):
        retriever = TesseraLangChainRetriever()
        docs = retriever.invoke("test")
        assert len(docs) == 1

    @patch("src.memory.recall_memories", return_value=[{"content": "x", "date": "", "category": "", "tags": "", "file_path": ""}])
    def test_top_k_override(self, mock_recall):
        retriever = TesseraLangChainRetriever(top_k=3)
        retriever.get_relevant_documents("q", top_k=10)
        mock_recall.assert_called_once_with("q", top_k=10)


class TestTesseraCrewAITool:
    def test_as_tool_structure(self):
        tool = TesseraCrewAITool()
        tool_dict = tool.as_tool()
        assert tool_dict["name"] == "tessera_knowledge"
        assert "description" in tool_dict
        assert callable(tool_dict["func"])

    @patch("src.core.recall", return_value="Found 2 memories")
    def test_tool_func_calls_recall(self, mock_recall):
        tool = TesseraCrewAITool(top_k=3)
        tool_dict = tool.as_tool()
        result = tool_dict["func"]("database")
        assert result == "Found 2 memories"


class TestTesseraAutoGenTool:
    def test_as_function_schema_structure(self):
        tool = TesseraAutoGenTool()
        schema = tool.as_function_schema()
        assert schema["name"] == "tessera_recall"
        assert "parameters" in schema
        assert schema["parameters"]["type"] == "object"
        assert "query" in schema["parameters"]["properties"]
        assert callable(schema["callable"])

    @patch("src.core.recall", return_value="Memory result")
    def test_callable_works(self, mock_recall):
        tool = TesseraAutoGenTool(top_k=5)
        schema = tool.as_function_schema()
        result = schema["callable"]("test query")
        assert result == "Memory result"


class TestGetAdapter:
    def test_langchain_adapter(self):
        adapter = get_adapter("langchain")
        assert isinstance(adapter, TesseraLangChainRetriever)

    def test_crewai_adapter(self):
        adapter = get_adapter("crewai")
        assert isinstance(adapter, TesseraCrewAITool)

    def test_autogen_adapter(self):
        adapter = get_adapter("autogen")
        assert isinstance(adapter, TesseraAutoGenTool)

    def test_unsupported_framework(self):
        with pytest.raises(ValueError, match="Unsupported framework"):
            get_adapter("unknown_framework")

    def test_case_insensitive(self):
        adapter = get_adapter("LangChain")
        assert isinstance(adapter, TesseraLangChainRetriever)


class TestGetAdapterInfo:
    def test_langchain_info(self):
        info = get_adapter_info("langchain")
        assert info["framework"] == "LangChain"
        assert "code" in info

    def test_unsupported_info(self):
        info = get_adapter_info("unknown")
        assert "error" in info
        assert "supported" in info


class TestAdapterCore:
    @patch("src.adapters.get_adapter_info")
    def test_core_get_agent_adapter(self, mock_info):
        from src.core import get_agent_adapter

        mock_info.return_value = {
            "framework": "LangChain",
            "description": "Use Tessera as a LangChain retriever.",
            "install": "pip install langchain project-tessera",
            "code": "from src.adapters import TesseraLangChainRetriever",
        }
        result = get_agent_adapter("langchain")
        assert "Tessera LangChain Adapter" in result
        assert "pip install" in result

    def test_core_unsupported_framework(self):
        from src.core import get_agent_adapter

        result = get_agent_adapter("unknown")
        assert "Error" in result
        assert "Supported" in result


class TestAdapterHTTP:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    @patch("src.core.get_agent_adapter", return_value="LangChain adapter info")
    def test_adapter_endpoint(self, mock_adapter):
        resp = self.client.get("/adapters/langchain")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_adapter.assert_called_once_with("langchain")
