from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert software project dependency analyzer for TaskFlow Pro.
Your task is to analyze a closed set of project tasks and propose realistic prerequisite dependencies.

CRITICAL RULES:
1. Closed-set grounding: You may ONLY use the exact Task IDs provided in the user prompt. DO NOT invent task IDs.
2. Direction: If Task B cannot start until Task A finishes, then Task B depends on Task A.
   Output: "task_id": "B", "prerequisite_id": "A".
3. Evidence required: Every suggestion MUST cite the exact phrase or reason from the task title/description.
4. Abstention allowed: If no clear logical dependency exists, return an empty array [].
5. Output format: Return strictly a valid JSON array of objects conforming to the schema below. No markdown fences, no conversational text.

JSON Schema:
[
  {
    "task_id": "<dependent_task_id>",
    "prerequisite_id": "<prerequisite_task_id>",
    "rationale": "<evidence and reason>",
    "confidence": <float between 0.0 and 1.0>
  }
]
"""

FEW_SHOT_EXAMPLE = """
Example:
Tasks:
- ID: task-db, Title: Database Schema, Description: Design SQL tables
- ID: task-api, Title: Backend Endpoints, Description: Build CRUD endpoints using database tables
- ID: task-test, Title: Integration Tests, Description: Test endpoints against database

Output:
[
  {"task_id": "task-api", "prerequisite_id": "task-db", "rationale": "CRUD endpoints require database tables to be designed first.", "confidence": 0.95},
  {"task_id": "task-test", "prerequisite_id": "task-api", "rationale": "Integration tests require backend endpoints to be implemented first.", "confidence": 0.90}
]
"""


class LLMProvider:
    """
    Provider-agnostic LLM interface with fallback.
    Supports Gemini, OpenAI, or intelligent local heuristic parser.
    """

    @classmethod
    async def call_llm(cls, prompt: str) -> Optional[str]:
        # 1. Try Gemini if configured
        if settings.GEMINI_API_KEY:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n" + FEW_SHOT_EXAMPLE + "\n" + prompt}]}],
                    "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                logger.warning(f"Gemini API call failed, falling back: {e}")

        # 2. Try OpenAI if configured
        if settings.OPENAI_API_KEY:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
                payload = {
                    "model": "gpt-4o-mini",
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT + "\n" + FEW_SHOT_EXAMPLE},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        return content
            except Exception as e:
                logger.warning(f"OpenAI API call failed, falling back: {e}")

        # Fallback to local heuristic rule engine
        return None

    @classmethod
    def local_heuristic_suggestions(
        cls,
        tasks: List[Dict[str, Any]],
        existing_edges: List[Tuple[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        Deterministic, offline semantic dependency suggester when no external LLM key is configured.
        Follows standard software engineering lifecycle dependencies.
        """
        existing_set = set(existing_edges)
        suggestions: List[Dict[str, Any]] = []

        # Keywords patterns
        # If task A has 'pattern_a' and task B has 'pattern_b', B depends on A
        patterns = [
            ("arch", "api", "API architecture must be established before building endpoints.", 0.95),
            ("arch", "ui", "System architecture defines data requirements for UI components.", 0.85),
            ("db", "api", "Backend endpoints depend on database schema and migrations.", 0.95),
            ("auth", "api", "Protected API endpoints depend on authentication mechanism.", 0.90),
            ("api", "integ", "Integration testing requires working API endpoints.", 0.95),
            ("ui", "kanban", "Kanban board interface builds upon foundational UI components.", 0.88),
            ("integ", "perf", "Performance benchmarks run after integration tests pass.", 0.85),
            ("perf", "deploy", "Production deployment requires performance validation.", 0.92),
            ("api", "ai", "AI suggestion engine interfaces with backend API data models.", 0.85),
        ]

        task_map = {t["id"]: t for t in tasks}

        for p_key, t_key, rationale, conf in patterns:
            # Find matching tasks
            prereq_candidates = [
                t["id"] for t in tasks
                if p_key in t["id"].lower() or p_key in t["title"].lower() or p_key in t["description"].lower()
            ]
            dependent_candidates = [
                t["id"] for t in tasks
                if t_key in t["id"].lower() or t_key in t["title"].lower() or t_key in t["description"].lower()
            ]

            for prereq_id in prereq_candidates:
                for dep_id in dependent_candidates:
                    if prereq_id != dep_id and (dep_id, prereq_id) not in existing_set:
                        # Avoid duplicates in suggestion list
                        if not any(s["task_id"] == dep_id and s["prerequisite_id"] == prereq_id for s in suggestions):
                            suggestions.append({
                                "task_id": dep_id,
                                "prerequisite_id": prereq_id,
                                "rationale": f"Citing '{task_map[dep_id]['title']}': {rationale}",
                                "confidence": conf,
                            })

        return suggestions
