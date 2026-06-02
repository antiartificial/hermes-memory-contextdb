"""
ContextDB Memory Provider for Hermes Agent

Primary memory backend using ContextDB with epistemic features
(credibility, source tracking, narrative retrieval).

Supports both embedded (BadgerDB) and Postgres + pgvector backends.
Credentials should be stored in ~/.hermes/.env
"""

from __future__ import annotations

import datetime
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from contextdb import ContextDB

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)


def _get_contextdb_url() -> Optional[str]:
    """
    Resolve ContextDB connection URL.

    Priority:
    1. CONTEXTDB_URL (full connection string)
    2. Build from CONTEXTDB_HOST / PORT / USER / PASSWORD / DATABASE
    3. Return None → ContextDB will use embedded mode
    """
    # Full URL takes precedence
    if url := os.getenv("CONTEXTDB_URL"):
        return url

    host = os.getenv("CONTEXTDB_HOST")
    if not host:
        return None  # No Postgres config → use embedded

    port = os.getenv("CONTEXTDB_PORT", "5432")
    user = os.getenv("CONTEXTDB_USER", "hermes")
    password = os.getenv("CONTEXTDB_PASSWORD", "")
    database = os.getenv("CONTEXTDB_DATABASE", "hermes_contextdb")

    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    else:
        return f"postgresql://{user}@{host}:{port}/{database}"


class ContextDBMemoryProvider(MemoryProvider):
    name = "contextdb"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.db: Optional[ContextDB] = None
        self.namespace = self.config.get("namespace", "hermes-agent")
        self.mode = self.config.get("mode", "agent_memory")
        self._current_session_id: Optional[str] = None

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        self._current_session_id = session_id

        url = _get_contextdb_url()

        try:
            if url:
                logger.info(f"ContextDB connecting to Postgres: {url.split('@')[-1]}")
                self.db = ContextDB(url)
            else:
                logger.info("ContextDB using embedded mode (BadgerDB)")
                self.db = ContextDB()  # embedded

            # Ensure namespace exists with desired mode
            ns = self.db.namespace(self.namespace, mode=self.mode)
            logger.info(f"ContextDB ready | namespace={self.namespace} | mode={self.mode}")

        except Exception as e:
            logger.error(f"Failed to initialize ContextDB: {e}")
            self.db = None

    _CRED_SHORT = {"high": "hi", "medium": "med", "low": "lo"}

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self.db:
            return ""

        try:
            ns = self.db.namespace(self.namespace, mode=self.mode)
            results = ns.retrieve(text=query, top_k=6)

            if not results:
                return ""

            lines = []
            for r in results:
                conf = getattr(r, "confidence", 0.7)
                cred = getattr(r, "credibility", "medium")
                content = getattr(r, "content", str(r))[:300]
                props = getattr(r, "properties", None) or {}

                platform = props.get("platform")
                model = props.get("model")
                turn_id = props.get("turn_id", "")
                role = props.get("role")

                cred_str = self._CRED_SHORT.get(str(cred), str(cred)[:3])
                tag = f"[ctx] {int(conf * 100)}% {cred_str}"

                origin = "/".join(
                    p for p in (platform, model) if p and p != "unknown"
                )
                if origin:
                    tag += f" | {origin}"

                if turn_id:
                    short = turn_id if len(turn_id) <= 16 else turn_id[:16]
                    tag += f" {short}"

                if role:
                    tag += f" [{role[:4]}]"

                lines.append(f"{tag}\n  {content}")

            return f"<memory-context>\n" + "\n".join(lines) + "\n</memory-context>"

        except Exception as e:
            logger.warning(f"ContextDB prefetch failed: {e}")
            return ""

    def _get_auto_labels(self, role: str, extra_labels: Optional[List[str]] = None) -> List[str]:
        labels = ["hermes", "session"]
        if role in ("user", "assistant"):
            labels.append(role)
        if self._current_session_id:
            labels.append("agent")
        if extra_labels:
            labels.extend(l for l in extra_labels if l not in labels)
        return labels

    DEFAULT_CONFIDENCE_USER = 0.75
    DEFAULT_CONFIDENCE_ASSISTANT = 0.85

    def sync_turn(self, user_message: str, assistant_message: str, **kwargs) -> None:
        if not self.db:
            return
        try:
            ns = self.db.namespace(self.namespace, mode=self.mode)

            turn_id = kwargs.get("turn_id") or f"turn:{uuid.uuid4().hex[:12]}"
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"
            platform = kwargs.get("platform") or self.config.get("platform", "unknown")
            model = kwargs.get("model") or self.config.get("model", "unknown")
            extra_labels = kwargs.get("labels")

            session_tag = self._current_session_id or "ephemeral"
            source_id = f"hermes:{platform}:session:{session_tag}"

            user_confidence = kwargs.get("user_confidence", self.DEFAULT_CONFIDENCE_USER)
            assistant_confidence = kwargs.get("assistant_confidence", self.DEFAULT_CONFIDENCE_ASSISTANT)

            base_properties = {
                "session_id": self._current_session_id or "",
                "turn_id": turn_id,
                "timestamp": timestamp,
                "platform": platform,
                "model": model,
            }

            ns.write(
                content=user_message,
                source_id=source_id,
                confidence=user_confidence,
                labels=self._get_auto_labels("user", extra_labels),
                properties={**base_properties, "role": "user"},
            )

            ns.write(
                content=assistant_message,
                source_id=f"hermes:{platform}:model:{model}",
                confidence=assistant_confidence,
                labels=self._get_auto_labels("assistant", extra_labels),
                properties={**base_properties, "role": "assistant"},
            )
        except Exception as e:
            logger.warning(f"ContextDB sync_turn failed: {e}")
    def system_prompt_block(self) -> str:
        return (
            "Memory is powered by ContextDB — an epistemic knowledge base that tracks "
            "source credibility, confidence, and evidence chains."
        )

    # ---------------- Tools ----------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "contextdb_search",
                "description": "Search ContextDB with credibility awareness",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "default": 5},
                        "min_confidence": {"type": "number", "default": 0.4},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "contextdb_explain",
                "description": "Get a narrative explanation with sources and confidence from ContextDB",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                    },
                    "required": ["topic"],
                },
            },
            {
                "name": "contextdb_feedback",
                "description": "Provide feedback on a memory item to improve credibility scoring (new ContextDB v0.3+ feature)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string"},
                        "rating": {"type": "number", "description": "1.0 (helpful) to -1.0 (incorrect)"},
                        "note": {"type": "string", "default": ""},
                    },
                    "required": ["item_id", "rating"],
                },
            },
        ]

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> str:
        if not self.db:
            return "ContextDB is not available right now."

        try:
            ns = self.db.namespace(self.namespace, mode=self.mode)

            if name == "contextdb_search":
                results = ns.retrieve(
                    text=arguments["query"],
                    top_k=arguments.get("top_k", 5),
                    min_confidence=arguments.get("min_confidence", 0.4)
                )
                return "\n".join(
                    f"- (conf={getattr(r, 'confidence', 0.7):.0%}, src={getattr(r, 'source_id', '?')}) "
                    f"{getattr(r, 'content', r)[:200]}"
                    for r in results
                )

            elif name == "contextdb_explain":
                results = ns.retrieve(text=arguments["topic"], top_k=5)
                return "ContextDB narrative:\n" + "\n".join(
                    f"• {getattr(r, 'content', r)}" for r in results
                )

            elif name == "contextdb_feedback":
                try:
                    ns.feedback(
                        item_id=arguments["item_id"],
                        rating=arguments["rating"],
                        note=arguments.get("note", "")
                    )
                    return f"Feedback recorded for {arguments['item_id']}"
                except AttributeError:
                    return "Feedback API not available in this ContextDB version"

        except Exception as e:
            return f"ContextDB error: {e}"

        return "Unknown ContextDB tool"
