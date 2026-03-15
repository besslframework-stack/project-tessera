"""Agent framework adapters: LangChain, CrewAI, AutoGen integration.

Provides adapter classes that wrap Tessera's core recall/remember functions
into formats compatible with popular agent frameworks.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TesseraLangChainRetriever:
    """LangChain-compatible retriever that wraps Tessera's recall_memories.

    Usage:
        retriever = TesseraLangChainRetriever()
        docs = retriever.get_relevant_documents("my query")
    """

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    def get_relevant_documents(self, query: str, **kwargs: Any) -> list[dict]:
        """Retrieve documents relevant to the query.

        Args:
            query: Search query string.
            **kwargs: Additional keyword arguments (top_k override).

        Returns:
            List of dicts with page_content and metadata keys.
        """
        from src.memory import recall_memories

        top_k = kwargs.get("top_k", self.top_k)
        memories = recall_memories(query, top_k=top_k)

        documents = []
        for mem in memories:
            documents.append({
                "page_content": mem.get("content", ""),
                "metadata": {
                    "date": mem.get("date", ""),
                    "category": mem.get("category", ""),
                    "tags": mem.get("tags", ""),
                    "file_path": mem.get("file_path", ""),
                    "source": "tessera",
                },
            })
        return documents

    def invoke(self, query: str, **kwargs: Any) -> list[dict]:
        """Alias for get_relevant_documents (LangChain v2 interface)."""
        return self.get_relevant_documents(query, **kwargs)


class TesseraCrewAITool:
    """CrewAI-compatible tool that wraps Tessera remember/recall.

    Usage:
        tool = TesseraCrewAITool()
        tool_dict = tool.as_tool()
    """

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    def _recall(self, query: str) -> str:
        """Recall memories matching query."""
        from src.core import recall
        return recall(query, self.top_k)

    def _remember(self, content: str) -> str:
        """Remember new content."""
        from src.core import remember
        return remember(content)

    def as_tool(self) -> dict:
        """Return a CrewAI-compatible tool dict.

        Returns:
            Dict with name, description, and func keys.
        """
        return {
            "name": "tessera_knowledge",
            "description": (
                "Search and retrieve knowledge from Tessera personal knowledge base. "
                "Pass a natural language query to find relevant memories and documents."
            ),
            "func": self._recall,
        }


class TesseraAutoGenTool:
    """AutoGen-compatible tool that wraps Tessera functions.

    Usage:
        tool = TesseraAutoGenTool()
        schema = tool.as_function_schema()
    """

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    def _recall(self, query: str) -> str:
        """Recall memories matching query."""
        from src.core import recall
        return recall(query, self.top_k)

    def as_function_schema(self) -> dict:
        """Return an OpenAI function calling schema for AutoGen.

        Returns:
            Dict with name, description, parameters, and callable.
        """
        return {
            "name": "tessera_recall",
            "description": (
                "Recall knowledge from Tessera personal knowledge base. "
                "Returns relevant memories and documents matching the query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                },
                "required": ["query"],
            },
            "callable": self._recall,
        }


def get_adapter(framework: str) -> object:
    """Factory function to get the appropriate adapter.

    Args:
        framework: One of "langchain", "crewai", "autogen".

    Returns:
        Adapter instance for the specified framework.

    Raises:
        ValueError: If framework is not supported.
    """
    framework = framework.strip().lower()
    if framework == "langchain":
        return TesseraLangChainRetriever()
    elif framework == "crewai":
        return TesseraCrewAITool()
    elif framework == "autogen":
        return TesseraAutoGenTool()
    else:
        raise ValueError(
            f"Unsupported framework: {framework}. "
            f"Supported: langchain, crewai, autogen"
        )


def get_adapter_info(framework: str) -> dict:
    """Get setup instructions and code snippet for a framework adapter.

    Args:
        framework: One of "langchain", "crewai", "autogen".

    Returns:
        Dict with framework name, description, setup instructions, and code snippet.
    """
    framework = framework.strip().lower()

    adapters_info = {
        "langchain": {
            "framework": "LangChain",
            "description": "Use Tessera as a LangChain retriever for RAG pipelines.",
            "install": "pip install langchain project-tessera",
            "code": (
                "from src.adapters import TesseraLangChainRetriever\n"
                "\n"
                "retriever = TesseraLangChainRetriever(top_k=5)\n"
                "docs = retriever.get_relevant_documents('my query')\n"
                "\n"
                "# Use with LangChain chain:\n"
                "# from langchain.chains import RetrievalQA\n"
                "# chain = RetrievalQA.from_chain_type(\n"
                "#     llm=llm, retriever=retriever\n"
                "# )"
            ),
        },
        "crewai": {
            "framework": "CrewAI",
            "description": "Use Tessera as a CrewAI tool for agent tasks.",
            "install": "pip install crewai project-tessera",
            "code": (
                "from src.adapters import TesseraCrewAITool\n"
                "\n"
                "tessera = TesseraCrewAITool(top_k=5)\n"
                "tool = tessera.as_tool()\n"
                "\n"
                "# Use with CrewAI agent:\n"
                "# agent = Agent(\n"
                "#     role='Researcher',\n"
                "#     tools=[tool]\n"
                "# )"
            ),
        },
        "autogen": {
            "framework": "AutoGen",
            "description": "Use Tessera as an AutoGen function tool.",
            "install": "pip install pyautogen project-tessera",
            "code": (
                "from src.adapters import TesseraAutoGenTool\n"
                "\n"
                "tessera = TesseraAutoGenTool(top_k=5)\n"
                "schema = tessera.as_function_schema()\n"
                "\n"
                "# Register with AutoGen agent:\n"
                "# assistant.register_function(\n"
                "#     function_map={schema['name']: schema['callable']}\n"
                "# )"
            ),
        },
    }

    if framework not in adapters_info:
        return {
            "error": f"Unsupported framework: {framework}",
            "supported": list(adapters_info.keys()),
        }

    return adapters_info[framework]
