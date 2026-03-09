# Tessera Roadmap: v0.6.4 → v1.0.0

> **비전**: 모든 AI 대화에서 발생하는 지식을 캡처하고, 저장하고, 어떤 AI에게든 다시 서빙하는 Personal Knowledge Layer.
> MCP는 첫 번째 인터페이스일 뿐. 당신의 기억, 당신의 머신, 당신의 데이터.

---

## Phase 1: Sponge (v0.6.4 → v0.7.0) — Auto-Learn

메모리를 자동화한다. QMD와의 결정적 차이. QMD는 memory가 0이다. Tessera는 모든 상호작용에서 배운다.

| 버전 | Feature Name | 하는 일 | 코드 변경 | 비전에서의 의미 |
|------|-------------|---------|----------|---------------|
| **v0.6.4** | Interaction Log | MCP tool 호출 시 query + response 요약을 `data/interactions/` 에 자동 기록하는 SQLite 테이블 추가 | `src/interaction_log.py` 신규, `mcp_server.py`의 모든 tool 함수에 decorator 적용 | 자동 학습의 원재료 — 무엇이 오갔는지 기록해야 학습이 가능하다 |
| **v0.6.5** | Auto-Extract | interaction log에서 "결정", "선호", "사실" 패턴을 regex + 휴리스틱으로 추출, 자동으로 `learn_and_index` 호출 | `src/auto_extract.py` 신규 (패턴 매칭 엔진), `src/interaction_log.py`에 post-save hook 추가 | 사용자가 "remember" 안 해도 알아서 기억한다 |
| **v0.6.6** | Memory Dedup | 같은 내용의 memory 중복 저장 방지 — embedding cosine similarity > 0.92면 기존 memory에 merge | `src/memory.py`의 `save_memory()`에 dedup 로직 추가, `_check_duplicate()` 함수 | memory가 쌓이면 중복이 폭발한다. 자동 학습 전에 반드시 필요 |
| **v0.6.7** | Memory Categories | memory에 자동 카테고리 부여: `decision`, `preference`, `fact`, `reference`, `context` — 추출 패턴 기반 | `src/auto_extract.py`에 카테고리 분류 로직, `src/memory.py` frontmatter에 `category` 필드 추가 | 나중에 "내 결정 이력" 같은 쿼리에 필터로 쓰인다 |
| **v0.6.8** | Session Boundary | 같은 세션 내 interaction을 그룹핑하는 session_id 추가 — MCP 서버 시작 시 UUID 생성 | `mcp_server.py`에 `_SESSION_ID` 추가, `src/interaction_log.py` 스키마에 session_id 컬럼 | "저번 세션에서 뭐 했지?" 질문에 답할 수 있는 기초 |
| **v0.6.9** | Session Summary | 세션 종료(서버 shutdown) 시 해당 세션의 interaction을 요약해서 memory로 자동 저장 | `mcp_server.py` lifespan `finally` 블록에 summary 생성 로직, `src/session_summary.py` 신규 | 세션 날아가도 핵심 내용은 영속된다 |
| **v0.7.0** | Sponge Mode | workspace.yaml에 `auto_learn: true/false` 설정, 자동 학습 on/off 토글 MCP tool 추가, 학습된 항목 리뷰 tool | `src/config.py`에 `AutoLearnConfig` dataclass, `mcp_server.py`에 `toggle_auto_learn`, `review_learned` tool 추가 | Phase 1 완성 — Tessera가 스스로 배우는 시스템 |

---

## Phase 2: Radar (v0.7.1 → v0.8.0) — Intelligence Layer

검색 도구에서 지식 시스템으로. 맥락을 이해하고, 시간 흐름을 추적하고, 적절한 타이밍에 적절한 지식을 서빙한다.

| 버전 | Feature Name | 하는 일 | 코드 변경 | 비전에서의 의미 |
|------|-------------|---------|----------|---------------|
| **v0.7.1** | Temporal Index | memory와 document에 시간 축 인덱스 추가 — "지난주에 결정한 것" 같은 시간 기반 쿼리 지원 | `src/memory.py`와 `src/search.py`에 `since`/`until` 파라미터 추가, LanceDB metadata에 `created_at` 필드 정규화 | 기억은 시간 순서가 있어야 의미가 있다 |
| **v0.7.2** | Decision Tracker | 동일 주제에 대한 결정 변화를 추적 — "X에 대한 결정이 어떻게 바뀌었는지" 타임라인 조회 | `src/decision_tracker.py` 신규, category=decision인 memory를 topic별로 그룹핑 + 시간순 정렬 | AI가 과거 결정과 현재 결정의 모순을 감지할 수 있는 기초 |
| **v0.7.3** | Contradiction Detector | 새 memory 저장 시 기존 memory와 의미적으로 반대되는 내용이 있으면 경고 반환 | `src/contradiction.py` 신규 — 같은 topic의 memory를 가져와 부정 패턴("~하지 않기로", "대신") 감지 | "전에는 A로 결정했는데 지금 B라고 하셨는데, 변경 맞으세요?" |
| **v0.7.4** | Context Window | unified_search에 현재 대화 맥락(최근 3개 query)을 자동으로 포함시켜 검색 정확도 향상 | `mcp_server.py`에 `_recent_queries` deque(maxlen=3), `unified_search`에서 query 확장 로직 | 단발 검색 → 맥락 인식 검색으로 전환 |
| **v0.7.5** | Smart Suggest | 현재 대화 주제와 관련된 과거 memory/document를 능동적으로 추천하는 MCP tool | `mcp_server.py`에 `proactive_suggest` tool 추가 — `_recent_queries` 기반으로 관련 지식 자동 서핑 | AI가 "참고로 이전에 이런 내용이 있었습니다"를 할 수 있다 |
| **v0.7.6** | Relevance Decay | 오래된 memory의 검색 가중치를 시간에 따라 감쇠 — 최근 정보가 우선 노출 | `src/search.py`와 `src/memory.py`의 similarity 계산에 `time_decay_factor` 적용 | 6개월 전 결정보다 어제 결정이 더 관련도가 높아야 한다 |
| **v0.7.7** | Topic Map | 축적된 memory와 document에서 자동으로 topic 클러스터를 생성하고, topic 간 관계를 맵핑 | `src/topic_map.py` 신규 — embedding 기반 K-means 클러스터링 + 대표 키워드 추출 | knowledge graph의 자동 생성 버전 — 사용자가 안 만들어도 지식 구조가 보인다 |
| **v0.7.8** | Knowledge Stats | 축적된 지식의 통계 대시보드 — topic별 memory 수, 시간대별 학습량, 가장 많이 조회된 지식 | `mcp_server.py`에 `knowledge_stats` tool, `src/knowledge_stats.py` 신규 | 사용자가 "내 지식 베이스"의 상태를 한눈에 볼 수 있다 |
| **v0.8.0** | Radar Complete | Phase 2 통합 — Intelligence Layer 기능을 `tessera check` CLI에서 전체 진단, proactive suggest를 MCP instructions에 반영 | `src/cli.py`에 `intelligence` 서브커맨드, `mcp_server.py` instructions 업데이트 | 검색 도구가 아닌 지식 시스템으로 완전 전환 |

---

## Phase 3: Gateway (v0.8.1 → v0.9.0) — Beyond MCP

MCP 밖으로 나간다. HTTP API 서버를 추가해서 ChatGPT, 브라우저 확장, Raycast 등 어떤 클라이언트든 Tessera의 지식에 접근할 수 있게 한다.

| 버전 | Feature Name | 하는 일 | 코드 변경 | 비전에서의 의미 |
|------|-------------|---------|----------|---------------|
| **v0.8.1** | Core API Module | 기존 MCP tool 로직을 `src/api/core.py`로 분리 — MCP server와 HTTP server가 같은 코어를 공유 | `src/api/__init__.py`, `src/api/core.py` 신규 — `mcp_server.py`에서 비즈니스 로직 추출, MCP tool은 thin wrapper로 전환 | 하나의 코어, 여러 인터페이스 — 아키텍처의 전환점 |
| **v0.8.2** | HTTP Server | FastAPI 기반 HTTP API 서버 — `/search`, `/remember`, `/recall`, `/learn`, `/health` 엔드포인트 | `src/api/http_server.py` 신규, `pyproject.toml`에 `fastapi`, `uvicorn` optional dependency 추가 | ChatGPT Custom GPT에서 Tessera를 호출할 수 있다 |
| **v0.8.3** | API Auth | Bearer token 기반 인증 — `TESSERA_API_KEY` 환경변수, local-only일 때는 localhost 바인딩으로 우회 | `src/api/auth.py` 신규, `src/api/http_server.py`에 middleware 추가 | 로컬 네트워크에서도 다른 앱이 무단 접근 못한다 |
| **v0.8.4** | CLI Serve | `tessera serve --http` 로 HTTP 서버 시작, `--mcp`로 MCP 서버 시작, 기본은 둘 다 | `src/cli.py`의 `cmd_serve` 확장, HTTP + MCP 동시 실행 로직 | 하나의 커맨드로 모든 인터페이스 가동 |
| **v0.8.5** | OpenAPI Spec | HTTP API에 OpenAPI 3.0 스펙 자동 생성 — ChatGPT Actions, Raycast 등에서 import 가능 | FastAPI의 자동 생성 + `src/api/http_server.py`에 커스텀 스키마 보강 | ChatGPT Custom GPT 설정에 URL만 넣으면 바로 연동 |
| **v0.8.6** | Ingest API | HTTP API로 문서 업로드 + 인덱싱 — `POST /ingest` (multipart file upload) | `src/api/http_server.py`에 ingest 엔드포인트, temp 파일 저장 → pipeline 실행 → cleanup | 브라우저 확장에서 웹 페이지를 Tessera에 직접 저장할 수 있다 |
| **v0.8.7** | Webhook Support | 외부 이벤트(파일 변경, 새 대화 등)를 수신하는 webhook 엔드포인트 — `POST /webhook/ingest` | `src/api/http_server.py`에 webhook 엔드포인트, payload 파싱 → auto-ingest 또는 auto-learn 트리거 | Obsidian 플러그인, 자동화 스크립트 등에서 Tessera를 트리거할 수 있다 |
| **v0.8.8** | SSE Stream | Server-Sent Events로 실시간 알림 — 새 memory 저장, sync 완료, contradiction 감지 시 클라이언트에 push | `src/api/http_server.py`에 `/events` SSE 엔드포인트, `src/event_bus.py` 신규 (in-process pub/sub) | 브라우저 확장이 "방금 새로운 지식이 저장됐습니다"를 알 수 있다 |
| **v0.9.0** | Gateway Complete | Phase 3 통합 — `tessera serve` 기본 모드에서 MCP + HTTP 동시 가동, health check에 API 상태 포함 | `src/cli.py`, `mcp_server.py` 통합, `pyproject.toml` scripts에 `tessera-api` 추가 | "Claude Desktop tool"에서 "personal AI memory infrastructure"로 전환 완료 |

---

## Phase 4: Cortex (v0.9.1 → v1.0.0) — Persistent Brain

완전한 시스템. 축적된 지식에서 사용자 프로필 자동 구축. Cross-AI memory. AI가 문서가 아니라 당신을 기억한다.

| 버전 | Feature Name | 하는 일 | 코드 변경 | 비전에서의 의미 |
|------|-------------|---------|----------|---------------|
| **v0.9.1** | User Profile Schema | 사용자 프로필 스키마 정의 — preferences, expertise, communication_style, active_projects, decisions | `src/user_profile.py` 신규, `data/profile.json` 자동 생성 | AI가 "이 사람은 디자이너이고, 간결한 답변을 선호하고, 현재 X 프로젝트 중"임을 안다 |
| **v0.9.2** | Profile Auto-Build | 축적된 memory에서 프로필 자동 구축 — category=preference인 memory 분석, 빈도 기반 expertise 추론 | `src/user_profile.py`에 `build_from_memories()`, 주기적 rebuild 로직 | 사용자가 직접 프로필을 작성할 필요 없다 |
| **v0.9.3** | Profile MCP Tool | `who_am_i` MCP tool — AI가 대화 시작 시 사용자 프로필을 조회해서 맥락화된 응답 가능 | `mcp_server.py`에 `who_am_i` tool, MCP instructions에 "세션 시작 시 who_am_i 호출" 추가 | "Claude, 나 기억해?" → "네, 11년차 프로덕트 디자이너시고..." |
| **v0.9.4** | Cross-AI Format | memory export/import 포맷을 ChatGPT memory JSON, Gemini context 포맷과 호환되도록 변환기 추가 | `src/cross_ai.py` 신규 — `export_for_chatgpt()`, `import_from_chatgpt()`, 표준 포맷 정의 | 오늘 Claude로 일하고 내일 ChatGPT로 바꿔도 같은 memory |
| **v0.9.5** | Obsidian Export | memory와 knowledge graph를 Obsidian vault로 export — markdown + wikilink 형식, 자동 태그 | `src/export_obsidian.py` 신규, `mcp_server.py`에 `export_to_obsidian` tool 추가 | 지식이 Tessera 안에만 갇히지 않는다 — 사용자 소유의 데이터 |
| **v0.9.6** | Conversation Import | ChatGPT/Claude/Gemini 대화 내보내기 파일(JSON)을 Tessera에 import → auto-extract → memory화 | `src/conversation_import.py` 신규, `src/api/http_server.py`에 `POST /import/conversation` 추가 | 과거 AI 대화에서도 지식을 회수할 수 있다 |
| **v0.9.7** | Memory Vault | memory를 암호화 저장하는 옵션 — `TESSERA_VAULT_KEY` 환경변수로 AES-256 암호화, 로컬 전용 | `src/vault.py` 신규, `src/memory.py`에서 읽기/쓰기 시 vault layer 통과 | 개인 지식이므로 보안이 필요하다 — 클라우드 없이 로컬 암호화 |
| **v0.9.8** | Migration Tool | v0.6.x → v1.0.0 데이터 마이그레이션 — LanceDB 스키마 변경, memory frontmatter 정규화 | `src/migrate.py` 신규, `tessera migrate` CLI 커맨드 | 기존 사용자가 데이터 잃지 않고 업그레이드할 수 있다 |
| **v0.9.9** | Polish & Harden | 전체 에러 핸들링 강화, 로깅 정리, 테스트 커버리지 200개 이상, pyproject.toml classifiers를 Beta로 변경 | `tests/` 전반, `src/` 전반 에러 핸들링, `pyproject.toml` status 변경 | 1.0 출시 전 안정성 확보 |
| **v1.0.0** | Cortex GA | 첫 정식 릴리스 — PyPI v1.0.0, 통합 CLI (`tessera serve`로 MCP+HTTP), 프로필+자동학습+지식시스템+멀티AI 지원 | `pyproject.toml` version bump, description을 "Personal Knowledge Layer" 로 변경, keywords 확장 | AI가 당신의 문서가 아니라 당신을 기억한다 |

---

## 요약: 각 Phase가 만드는 차이

| Phase | 이전 | 이후 |
|-------|------|------|
| **Sponge** | 사용자가 "기억해"라고 해야 기억 | 대화하면 알아서 배움 |
| **Radar** | 키워드 검색 → 결과 반환 | 맥락 인식, 시간 추적, 모순 감지 |
| **Gateway** | Claude Desktop에서만 사용 가능 | 어떤 AI, 어떤 도구에서든 접근 |
| **Cortex** | 문서 검색 도구 | 나를 아는 AI 기억 시스템 |

## QMD 대비 경쟁 우위

| 기능 | QMD | Tessera v1.0 |
|------|-----|-------------|
| Document search | O | O (hybrid search + version ranking + dedup) |
| Memory | X | 자동 학습 + 수동 저장 + 태그 + 카테고리 |
| Cross-session | X | session summary + interaction log |
| Contradiction detection | X | O |
| HTTP API | X | O (ChatGPT, Raycast, 확장 프로그램) |
| User profile | X | 자동 구축 |
| Cross-AI | X | ChatGPT/Claude/Gemini memory 호환 |
| Obsidian export | X | O |
| Local-first encryption | X | AES-256 vault |

## 일정 추정

- Phase 1 (7 versions): 2-3주
- Phase 2 (9 versions): 3-4주
- Phase 3 (9 versions): 3-4주
- Phase 4 (10 versions): 4-5주
- **총: 12-16주 (약 3-4개월)**

1인 팀 기준. 각 버전은 1-3일 작업량. 테스트 포함.
