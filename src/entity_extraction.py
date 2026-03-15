"""Entity extraction: detect subject-predicate-object triples from text.

Uses regex + pattern matching (no LLM calls) to extract entities and
relationships from memories. This powers the Nexus knowledge graph.

Supported patterns:
- Technology choice: "chose PostgreSQL for Project X"
- Replacement: "switched from MySQL to PostgreSQL"
- Dependency: "Project X depends on Redis"
- Ownership: "Alice manages the backend team"
- Korean equivalents for all patterns
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """An extracted entity (person, technology, project, etc.)."""

    name: str
    entity_type: str  # person, technology, project, organization, concept

    def __hash__(self) -> int:
        return hash(self.name.lower())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.name.lower() == other.name.lower()


@dataclass
class Triple:
    """A subject-predicate-object relationship."""

    subject: Entity
    predicate: str  # chosen_for, replaced_by, depends_on, manages, uses, etc.
    object: Entity
    confidence: float = 0.8


# ---------------------------------------------------------------------------
# Known technology names (for entity type detection)
# ---------------------------------------------------------------------------

_TECH_NAMES = {
    # Databases
    "postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite",
    "dynamodb", "cassandra", "elasticsearch", "neo4j", "lancedb",
    "supabase", "firebase", "mariadb", "cockroachdb", "timescaledb",
    # Languages
    "python", "javascript", "typescript", "java", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "dart", "scala",
    "elixir", "clojure", "haskell", "lua", "r",
    # Frameworks
    "react", "vue", "angular", "svelte", "nextjs", "next.js", "nuxt",
    "django", "flask", "fastapi", "express", "nestjs", "spring",
    "rails", "laravel", "flutter", "swiftui", "jetpack compose",
    # Infrastructure
    "docker", "kubernetes", "k8s", "terraform", "aws", "gcp", "azure",
    "vercel", "netlify", "railway", "heroku", "cloudflare",
    "nginx", "caddy", "traefik", "github actions", "jenkins",
    # Tools
    "git", "github", "gitlab", "jira", "linear", "figma", "notion",
    "slack", "vscode", "vim", "neovim", "obsidian",
    # AI/ML
    "openai", "anthropic", "claude", "chatgpt", "gemini", "copilot",
    "langchain", "llamaindex", "huggingface", "pytorch", "tensorflow",
}

# ---------------------------------------------------------------------------
# Extraction patterns (English)
# ---------------------------------------------------------------------------

_EN_CHOICE_PATTERNS = [
    # "chose/selected/decided on X for Y"
    re.compile(
        r"(?:chose|selected|decided\s+on|picked|went\s+with)\s+"
        r"([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*)?)\s+"
        r"(?:for|in|on|as)\s+(?:the\s+)?(.{3,80}?)(?:\.|,|$)",
        re.IGNORECASE,
    ),
    # "use/using X for Y"
    re.compile(
        r"(?:use|using|adopt(?:ed|ing)?)\s+"
        r"([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*)?)\s+"
        r"(?:for|in|on|as)\s+(?:the\s+)?(.{3,80}?)(?:\.|,|$)",
        re.IGNORECASE,
    ),
]

_EN_REPLACEMENT_PATTERNS = [
    # "switched/migrated from X to Y"
    re.compile(
        r"(?:switch(?:ed)?|migrat(?:ed?|ing)|mov(?:ed?|ing)|chang(?:ed?|ing))\s+"
        r"(?:from\s+)?([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*)?)\s+"
        r"(?:to|with)\s+([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*)?)",
        re.IGNORECASE,
    ),
    # "replaced X with Y"
    re.compile(
        r"replace[ds]?\s+"
        r"([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*)?)\s+"
        r"with\s+([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*)?)",
        re.IGNORECASE,
    ),
]

_EN_DEPENDENCY_PATTERNS = [
    # "X depends on/requires/needs Y"
    re.compile(
        r"([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*)?)\s+"
        r"(?:depends?\s+on|requires?|needs?)\s+"
        r"([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*)?)",
        re.IGNORECASE,
    ),
]

_EN_OWNERSHIP_PATTERNS = [
    # "X manages/leads/owns/created Y"
    re.compile(
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+"
        r"(?:manages?|leads?|owns?|created?|built|maintains?)\s+"
        r"(?:the\s+)?(.{3,80}?)(?:\.|,|$)",
        re.IGNORECASE,
    ),
]

# ---------------------------------------------------------------------------
# Extraction patterns (Korean)
# ---------------------------------------------------------------------------

_KO_CHOICE_PATTERNS = [
    # "X를 Y에 사용/적용/도입"
    re.compile(r"(\S{2,30})(?:을|를)\s+(\S{2,30})(?:에|으로)\s*(?:사용|적용|도입|채택)"),
    # "Y에 X 사용/적용"
    re.compile(r"(\S{2,30})(?:에|에서)\s+(\S{2,30})(?:을|를)?\s*(?:사용|적용|도입|채택)"),
]

_KO_REPLACEMENT_PATTERNS = [
    # "X에서 Y로 전환/변경/이전"
    re.compile(r"(\S{2,30})(?:에서)\s+(\S{2,30})(?:으?로)\s*(?:전환|변경|이전|교체|마이그레이션)"),
]

_KO_DEPENDENCY_PATTERNS = [
    # "X는 Y에 의존/필요"
    re.compile(r"(\S{2,30})(?:은|는)\s+(\S{2,30})(?:에|을|를)\s*(?:의존|필요로|요구)"),
]

_KO_OWNERSHIP_PATTERNS = [
    # "X가 Y를 담당/관리/개발"
    re.compile(r"(\S{2,30})(?:이|가)\s+(\S{2,30})(?:을|를)\s*(?:담당|관리|개발|운영|리드)"),
]


# ---------------------------------------------------------------------------
# Entity type detection
# ---------------------------------------------------------------------------

def _detect_entity_type(name: str) -> str:
    """Detect entity type from name."""
    lower = name.lower().strip()

    # Known technology
    if lower in _TECH_NAMES:
        return "technology"

    # Version-suffixed tech (e.g., "Python 3.11", "React 18")
    base = re.sub(r"\s*[\d.]+$", "", lower)
    if base in _TECH_NAMES:
        return "technology"

    # Korean project/team/service suffixes
    if re.search(r"(프로젝트|팀|서비스|시스템|모듈|엔진|서버|앱|플랫폼)$", name):
        return "project"

    # English project indicators
    if re.search(r"(?:project|team|service|app|platform|module)\b", lower):
        return "project"

    # Capitalized multi-word that looks like a person
    if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+$", name):
        return "person"

    # Korean person names (2-4 chars, all Korean)
    if re.match(r"^[가-힣]{2,4}$", name) and len(name) <= 4:
        return "person"

    return "concept"


def _clean_entity_name(name: str) -> str:
    """Clean up extracted entity name."""
    name = name.strip()
    # Remove trailing punctuation
    name = re.sub(r"[.,;:!?]+$", "", name)
    # Remove leading articles
    name = re.sub(r"^(?:the|a|an)\s+", "", name, flags=re.IGNORECASE)
    # Remove trailing particles (Korean)
    name = re.sub(r"[은는이가을를에서로의]$", "", name)
    return name.strip()


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_triples(text: str) -> list[Triple]:
    """Extract entity-relationship triples from text.

    Scans text for patterns indicating relationships between entities
    (technology choices, replacements, dependencies, ownership).
    Returns a list of Triple objects.

    No LLM calls — pure regex + heuristics.
    """
    if not text or len(text) < 5:
        return []

    triples: list[Triple] = []

    # --- English choice patterns ---
    for pattern in _EN_CHOICE_PATTERNS:
        for match in pattern.finditer(text):
            subj_name = _clean_entity_name(match.group(1))
            obj_name = _clean_entity_name(match.group(2))
            if len(subj_name) < 2 or len(obj_name) < 2:
                continue
            triples.append(Triple(
                subject=Entity(subj_name, _detect_entity_type(subj_name)),
                predicate="chosen_for",
                object=Entity(obj_name, _detect_entity_type(obj_name)),
                confidence=0.85,
            ))

    # --- English replacement patterns ---
    for pattern in _EN_REPLACEMENT_PATTERNS:
        for match in pattern.finditer(text):
            old_name = _clean_entity_name(match.group(1))
            new_name = _clean_entity_name(match.group(2))
            if len(old_name) < 2 or len(new_name) < 2:
                continue
            triples.append(Triple(
                subject=Entity(old_name, _detect_entity_type(old_name)),
                predicate="replaced_by",
                object=Entity(new_name, _detect_entity_type(new_name)),
                confidence=0.85,
            ))

    # --- English dependency patterns ---
    for pattern in _EN_DEPENDENCY_PATTERNS:
        for match in pattern.finditer(text):
            subj_name = _clean_entity_name(match.group(1))
            obj_name = _clean_entity_name(match.group(2))
            if len(subj_name) < 2 or len(obj_name) < 2:
                continue
            triples.append(Triple(
                subject=Entity(subj_name, _detect_entity_type(subj_name)),
                predicate="depends_on",
                object=Entity(obj_name, _detect_entity_type(obj_name)),
                confidence=0.80,
            ))

    # --- English ownership patterns ---
    for pattern in _EN_OWNERSHIP_PATTERNS:
        for match in pattern.finditer(text):
            subj_name = _clean_entity_name(match.group(1))
            obj_name = _clean_entity_name(match.group(2))
            if len(subj_name) < 2 or len(obj_name) < 2:
                continue
            triples.append(Triple(
                subject=Entity(subj_name, _detect_entity_type(subj_name)),
                predicate="manages",
                object=Entity(obj_name, _detect_entity_type(obj_name)),
                confidence=0.75,
            ))

    # --- Korean choice patterns ---
    for pattern in _KO_CHOICE_PATTERNS:
        for match in pattern.finditer(text):
            g1 = _clean_entity_name(match.group(1))
            g2 = _clean_entity_name(match.group(2))
            if len(g1) < 2 or len(g2) < 2:
                continue
            triples.append(Triple(
                subject=Entity(g1, _detect_entity_type(g1)),
                predicate="chosen_for",
                object=Entity(g2, _detect_entity_type(g2)),
                confidence=0.80,
            ))

    # --- Korean replacement patterns ---
    for pattern in _KO_REPLACEMENT_PATTERNS:
        for match in pattern.finditer(text):
            old_name = _clean_entity_name(match.group(1))
            new_name = _clean_entity_name(match.group(2))
            if len(old_name) < 2 or len(new_name) < 2:
                continue
            triples.append(Triple(
                subject=Entity(old_name, _detect_entity_type(old_name)),
                predicate="replaced_by",
                object=Entity(new_name, _detect_entity_type(new_name)),
                confidence=0.80,
            ))

    # --- Korean dependency patterns ---
    for pattern in _KO_DEPENDENCY_PATTERNS:
        for match in pattern.finditer(text):
            subj_name = _clean_entity_name(match.group(1))
            obj_name = _clean_entity_name(match.group(2))
            if len(subj_name) < 2 or len(obj_name) < 2:
                continue
            triples.append(Triple(
                subject=Entity(subj_name, _detect_entity_type(subj_name)),
                predicate="depends_on",
                object=Entity(obj_name, _detect_entity_type(obj_name)),
                confidence=0.75,
            ))

    # --- Korean ownership patterns ---
    for pattern in _KO_OWNERSHIP_PATTERNS:
        for match in pattern.finditer(text):
            subj_name = _clean_entity_name(match.group(1))
            obj_name = _clean_entity_name(match.group(2))
            if len(subj_name) < 2 or len(obj_name) < 2:
                continue
            triples.append(Triple(
                subject=Entity(subj_name, _detect_entity_type(subj_name)),
                predicate="manages",
                object=Entity(obj_name, _detect_entity_type(obj_name)),
                confidence=0.75,
            ))

    # Deduplicate triples (same subject+predicate+object)
    seen: set[tuple[str, str, str]] = set()
    unique: list[Triple] = []
    for t in triples:
        key = (t.subject.name.lower(), t.predicate, t.object.name.lower())
        if key not in seen:
            seen.add(key)
            unique.append(t)

    return unique
