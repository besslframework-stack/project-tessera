"""PRD quality auditor based on CLAUDE.md 13-section structure."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Expected PRD sections (H2 headers) from CLAUDE.md
_EXPECTED_SECTIONS = [
    "개요",
    "문제 정의",
    "목표",
    "성공 지표",
    "요구사항",
    "유저 플로우",
    "유저 행동",
    "상태",
    "화면 설계",
    "데이터 요구사항",
    "예외 케이스",
    "부록",
    "변경 이력",
]

# Period selector options that should be consistent across PRDs
_PERIOD_OPTIONS = {"1D", "1W", "3M", "6M", "1Y", "ALL"}

# Membership tiers
_MEMBERSHIP_TIERS = {"Free", "Basic", "Expert", "Fellow", "뉴런클럽", "블랙에디션"}


@dataclass
class AuditResult:
    file_path: str
    found_sections: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    has_mermaid_newline_bug: bool = False
    has_wireframe: bool = False
    has_exception_coverage: bool = False
    has_version_in_filename: bool = False
    has_changelog: bool = False
    score: float = 0.0

    def summary(self) -> str:
        lines = [
            f"PRD 감사 결과: {Path(self.file_path).name}",
            f"점수: {self.score:.0f}/100",
            f"",
            f"섹션 완성도: {len(self.found_sections)}/{len(_EXPECTED_SECTIONS)}",
        ]
        if self.missing_sections:
            lines.append(f"  누락: {', '.join(self.missing_sections)}")
        if self.has_mermaid_newline_bug:
            lines.append("  [경고] Mermaid 다이어그램에 \\n 사용 (→ <br/> 변경 필요)")
        if not self.has_wireframe:
            lines.append("  [경고] 화면 설계에 와이어프레임(코드 블록) 없음")
        if not self.has_exception_coverage:
            lines.append("  [경고] 예외 케이스에 데이터/시스템 에러 미언급")
        if not self.has_version_in_filename:
            lines.append("  [경고] 파일명에 버전 번호 없음")
        if not self.has_changelog:
            lines.append("  [경고] 변경 이력 섹션 없음")
        for w in self.warnings:
            lines.append(f"  [참고] {w}")
        return "\n".join(lines)


def audit_prd_file(file_path: str | Path) -> AuditResult:
    """Audit a single PRD file against the 13-section structure."""
    file_path = Path(file_path)
    result = AuditResult(file_path=str(file_path))

    if not file_path.exists():
        result.warnings.append("파일이 존재하지 않습니다")
        return result

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="cp949", errors="replace")

    # 1. Check sections (H2 pattern matching)
    h2_headers = re.findall(r"^## (.+)", text, re.MULTILINE)
    h2_set = {h.strip().rstrip("#").strip() for h in h2_headers}

    for section in _EXPECTED_SECTIONS:
        # Fuzzy match: check if the expected section name appears in any H2
        matched = any(section in h for h in h2_set)
        if matched:
            result.found_sections.append(section)
        else:
            result.missing_sections.append(section)

    # 2. Mermaid \n bug check
    mermaid_blocks = re.findall(r"```mermaid(.*?)```", text, re.DOTALL)
    for block in mermaid_blocks:
        # Check for literal \n inside node labels (inside brackets)
        if re.search(r"\[.*?\\n.*?\]", block):
            result.has_mermaid_newline_bug = True
            break

    # 3. Wireframe check (code blocks in 화면 설계 section)
    screen_section = _extract_section(text, "화면 설계")
    if screen_section:
        result.has_wireframe = "```" in screen_section or "┌" in screen_section or "│" in screen_section

    # 4. Exception coverage
    exception_section = _extract_section(text, "예외 케이스")
    if exception_section:
        error_keywords = ["에러", "오류", "실패", "네트워크", "API", "타임아웃", "로딩"]
        result.has_exception_coverage = any(kw in exception_section for kw in error_keywords)

    # 5. Version in filename
    result.has_version_in_filename = bool(re.search(r"_v\d+", file_path.stem, re.IGNORECASE))

    # 6. Changelog section (fuzzy match since headers may have numbering like "13. 변경 이력")
    result.has_changelog = any("변경" in h and "이력" in h for h in h2_set)

    # Calculate score
    section_score = (len(result.found_sections) / len(_EXPECTED_SECTIONS)) * 60
    penalty = 0
    if result.has_mermaid_newline_bug:
        penalty += 5
    if not result.has_wireframe and "화면 설계" in result.found_sections:
        penalty += 5
    if not result.has_exception_coverage and "예외 케이스" in result.found_sections:
        penalty += 5
    if not result.has_version_in_filename:
        penalty += 5
    if not result.has_changelog:
        penalty += 5

    bonus = 0
    if result.has_wireframe:
        bonus += 5
    if result.has_exception_coverage:
        bonus += 5
    if result.has_version_in_filename:
        bonus += 5
    if result.has_changelog:
        bonus += 5

    result.score = max(0, min(100, section_score + bonus - penalty))
    return result


def find_prd_version_sprawl(project_root: str | Path) -> list[dict]:
    """Detect multiple versions of the same PRD in a directory.

    Returns list of dicts with 'base_name', 'versions', 'latest', 'archive_candidates'.
    """
    project_root = Path(project_root)
    if not project_root.exists():
        return []

    # Find all PRD files
    prd_files: list[Path] = []
    for md in project_root.rglob("*.md"):
        if "prd" in md.name.lower() or "PRD" in md.name:
            prd_files.append(md)

    # Group by base name (strip version)
    groups: dict[str, list[tuple[Path, tuple[int, ...]]]] = {}
    for f in prd_files:
        base = re.sub(r"_v\d+(?:\.\d+)*", "", f.stem, flags=re.IGNORECASE)
        ver_match = re.search(r"_v(\d+(?:\.\d+)*)", f.stem, re.IGNORECASE)
        ver = tuple(int(x) for x in ver_match.group(1).split(".")) if ver_match else (0,)
        groups.setdefault(base, []).append((f, ver))

    results = []
    for base, files in groups.items():
        if len(files) <= 1:
            continue

        files.sort(key=lambda x: x[1], reverse=True)
        latest = files[0]
        archive_candidates = [str(f[0]) for f in files[1:]]

        results.append({
            "base_name": base,
            "versions": [{"path": str(f[0]), "version": ".".join(str(v) for v in f[1])} for f in files],
            "latest": str(latest[0]),
            "archive_candidates": archive_candidates,
        })

    return results


def audit_cross_prd_consistency(project_root: str | Path) -> list[str]:
    """Check cross-PRD consistency for period selectors and tier access rules."""
    project_root = Path(project_root)
    if not project_root.exists():
        return []

    issues = []

    # Find all PRD files
    prd_files = list(project_root.rglob("*.md"))
    prd_files = [f for f in prd_files if "prd" in f.name.lower() or "PRD" in f.name]

    period_by_file: dict[str, set[str]] = {}
    tier_mentions: dict[str, set[str]] = {}

    for f in prd_files:
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        # Check period selector options
        period_matches = re.findall(r"(1D|1W|3M|6M|1Y|ALL)", text)
        if period_matches:
            period_by_file[str(f)] = set(period_matches)

        # Check tier mentions
        for tier in _MEMBERSHIP_TIERS:
            if tier in text:
                tier_mentions.setdefault(str(f), set()).add(tier)

    # Compare period options across files
    if len(period_by_file) > 1:
        all_periods = list(period_by_file.values())
        reference = all_periods[0]
        for fpath, periods in period_by_file.items():
            if periods != reference:
                issues.append(
                    f"기간 옵션 불일치: {Path(fpath).name} ({', '.join(sorted(periods))}) "
                    f"vs 기준 ({', '.join(sorted(reference))})"
                )

    return issues


def _extract_section(text: str, section_name: str) -> str | None:
    """Extract content of a specific H2 section."""
    pattern = rf"^## .*{re.escape(section_name)}.*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else None
