"""Test Knowledge Graph — the swarm's memory and token-optimization layer.

It serves the two purposes you asked for:

  1. GROUNDING — it indexes the whole framework (reusable steps, selectors,
     page objects, existing features) plus every test the swarm has generated,
     and hands the LLM the *relevant slice* so generated code stays consistent
     with what already exists.

  2. TOKEN OPTIMIZATION — instead of dumping the entire framework into every
     prompt, `retrieve_context()` returns only the pieces that overlap the
     requirement (scoped context). `find_reusable()` detects a near-duplicate
     of a past requirement so the swarm can reuse an existing test and skip the
     LLM entirely. Both are measured in estimated tokens saved and accumulated
     across runs.

Backed by a plain JSON file (.psi/knowledge-graph.json) so it works offline
with no database. Token counts are estimates (~4 chars/token) — enough to show
and compare savings without a tokenizer dependency.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / ".psi" / "knowledge-graph.json"

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "should", "is", "are", "to", "for", "with", "and", "of", "in", "on"}


def _toks(text: str) -> int:
    return max(1, len(text) // 4)


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class KnowledgeGraph:
    REUSE_THRESHOLD = 0.72   # requirement similarity above which we reuse a past test

    def __init__(self) -> None:
        self.framework = self._scan_framework()
        data = self._load()
        self.generations: list[dict] = data.get("generations", [])
        self.cumulative_tokens_saved: int = data.get("cumulative_tokens_saved", 0)

    # ---------------------------------------------------------------- scan
    def _scan_framework(self) -> dict:
        steps, selectors, pages, features = [], [], [], []

        for f in sorted((ROOT / "tests" / "steps").glob("*.py")):
            for m in re.finditer(r'@step\(\s*(?:parsers\.\w+\()?["\']([^"\']+)', f.read_text(encoding="utf-8")):
                steps.append(m.group(1))

        for f in sorted((ROOT / "framework" / "selectors").glob("*.py")):
            for m in re.finditer(r"^([A-Z][A-Z0-9_]+)\s*=", f.read_text(encoding="utf-8"), re.M):
                selectors.append(f"{f.stem}.{m.group(1)}")

        for f in sorted((ROOT / "framework" / "pages").glob("*.py")):
            for m in re.finditer(r"class\s+(\w+Page)\b", f.read_text(encoding="utf-8")):
                pages.append(m.group(1))

        for f in sorted((ROOT / "features").rglob("*.feature")):
            text = f.read_text(encoding="utf-8")
            for m in re.finditer(r"Scenario:\s*(.+)", text):
                features.append(m.group(1).strip())

        return {"steps": steps, "selectors": selectors, "pages": pages, "features": features}

    def full_context_tokens(self) -> int:
        """Tokens it would cost to dump the ENTIRE framework into a prompt."""
        blob = "\n".join(
            self.framework["steps"] + self.framework["selectors"]
            + self.framework["pages"] + self.framework["features"]
        )
        return _toks(blob)

    # ---------------------------------------------------------------- retrieve
    def retrieve_context(self, requirement: str, top_k: int = 6) -> dict:
        """Return only the framework pieces relevant to this requirement, so the
        LLM is grounded without paying for the whole framework."""
        rw = _words(requirement)

        def rank(items: list[str]) -> list[str]:
            scored = sorted(items, key=lambda s: _jaccard(rw, _words(s)), reverse=True)
            return [s for s in scored if _jaccard(rw, _words(s)) > 0][:top_k]

        steps = rank(self.framework["steps"]) or self.framework["steps"][:top_k]
        selectors = rank(self.framework["selectors"])
        pages = rank(self.framework["pages"])

        lines = ["# Reusable steps:", *(f"  - {s}" for s in steps)]
        if selectors:
            lines += ["# Selectors:", *(f"  - {s}" for s in selectors)]
        if pages:
            lines += ["# Page objects:", *(f"  - {p}" for p in pages)]
        text = "\n".join(lines)

        scoped = _toks(text)
        full = self.full_context_tokens()
        return {
            "text": text,
            "steps": steps,
            "selectors": selectors,
            "pages": pages,
            "scoped_tokens": scoped,
            "full_tokens": full,
            "tokens_saved": max(0, full - scoped),
        }

    # ---------------------------------------------------------------- reuse cache
    def find_reusable(self, requirement: str) -> dict | None:
        """A past generation whose requirement is a near-duplicate — reuse it and
        skip the LLM entirely (100% of that generation's tokens saved)."""
        rw = _words(requirement)
        best, best_score = None, 0.0
        for gen in self.generations:
            score = _jaccard(rw, _words(gen.get("requirement", "")))
            if score > best_score:
                best, best_score = gen, score
        if best and best_score >= self.REUSE_THRESHOLD:
            return {"score": round(best_score, 2), **best}
        return None

    # ---------------------------------------------------------------- record
    def record(self, requirement: str, scenario_id: str, cases: list, tokens_saved: int) -> None:
        self.generations = [g for g in self.generations if g.get("scenario_id") != scenario_id]
        self.generations.append(
            {"requirement": requirement, "scenario_id": scenario_id, "cases": cases}
        )
        self.cumulative_tokens_saved += max(0, tokens_saved)
        self._save()

    def token_report(self) -> dict:
        return {
            "generations_tracked": len(self.generations),
            "cumulative_tokens_saved": self.cumulative_tokens_saved,
            "framework_full_context_tokens": self.full_context_tokens(),
        }

    # ---------------------------------------------------------------- persistence
    def _load(self) -> dict:
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(
            json.dumps(
                {
                    "generations": self.generations,
                    "cumulative_tokens_saved": self.cumulative_tokens_saved,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
