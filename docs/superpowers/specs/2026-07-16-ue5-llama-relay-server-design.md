# UE5 ↔ llama.cpp 중계 FastAPI 서버 — 설계 문서

- **작성일:** 2026-07-16
- **상태:** 설계 승인됨 (구현 계획 대기)
- **목적:** UE5의 NPC가 로컬 LLM(llama.cpp)과 실시간으로 대화하도록, Python(FastAPI) 중계 서버를 만든다.

---

## 1. 배경 및 목표

UE5의 NPC가 플레이어와 실시간으로 대화한다. llama.cpp 서버는 `http://127.0.0.1:8080`에서 OpenAI 호환 API로 이미 구동 중이다. Python 서버는 그 사이를 중계하며, NPC별 성격과 플레이어별 대화 히스토리를 다룬다.

**범위:** 로컬 단일 프로세스 프로토타입. 저장·확장 지점은 인터페이스로 분리해 나중에 확장 가능하게 둔다.

### 핵심 설계 결정 (브레인스토밍 결과)

| # | 결정 | 선택 |
|---|---|---|
| 1 | 히스토리 지속성 | 인메모리로 시작, `HistoryStore` 인터페이스로 분리해 나중에 SQLite/파일 교체 |
| 2 | NPC 페르소나 소유 | **UE5(DataAsset)가 소유**, 요청마다 서버로 전송 |
| 3 | 히스토리 소유 | **서버가 소유**, `(player_id, npc_id)` 키로 보관 |
| 4 | 응답 방식 | 스트리밍 없음. `POST /chat` → JSON 하나 |
| 5 | 히스토리 관리 | 최근 N턴 슬라이딩 윈도우 (N은 설정값) |
| 6 | 오류 처리 | 항상 HTTP 200 + JSON 내 `ok`/`error` 필드. 타임아웃도 설정값 |

---

## 2. 아키텍처 개요

```
UE5 (NPC)  ──HTTP/JSON──▶  FastAPI 서버  ──OpenAI 호환 API──▶  llama.cpp (127.0.0.1:8080)
   │                          │
   │  npc_id, player_id,      │  ┌─ 히스토리 저장소 (인메모리, 교체 가능)
   │  system_prompt,          │  ├─ 프롬프트 조립 (persona + context + history)
   │  context, message        │  └─ llama.cpp 클라이언트 (타임아웃 처리)
   ▼                          ▼
 단순 JSON 응답  ◀────────────┘
```

**역할 분담:**

| 데이터 | 성격 | 사는 곳 |
|---|---|---|
| 페르소나 (system prompt) | 저작 데이터 (기획 콘텐츠) | UE5 DataAsset (요청마다 전송) |
| 상황 컨텍스트 | 매 턴 바뀌는 런타임 정보 | UE5 (요청마다 전송) |
| 대화 히스토리 | 런타임 상태 (LLM 로직과 결합) | Python 서버 (`player_id`+`npc_id` 키) |

---

## 3. API 계약

### `POST /chat` — 대화 한 턴

**요청**
```json
{
  "player_id": "player_42",
  "npc_id": "blacksmith_bob",
  "system_prompt": "너는 무뚝뚝한 대장장이 Bob이다. 말수가 적고 퉁명스럽다.",
  "context": "플레이어가 방금 잃어버린 망치를 돌려줬다. 고마워하는 중.",
  "message": "안녕, 대장장이 아저씨"
}
```

- `player_id`, `npc_id`, `system_prompt`, `message` — 필수
- `context` — 선택 (이번 턴 상황). 서버가 `system_prompt`와 합쳐 최종 system 메시지로 구성
- `message` — 플레이어의 이번 발화. 서버가 저장된 히스토리 뒤에 붙여 llama.cpp로 전달

**응답 (항상 HTTP 200)**
```json
// 성공
{ "reply": "흥, 또 왔군.", "ok": true, "npc_id": "blacksmith_bob", "turn_count": 3 }

// 실패
{ "reply": "", "ok": false, "error": "llm_unavailable", "npc_id": "blacksmith_bob" }
```

- `error` 값: `llm_unavailable` (llama.cpp 연결 실패) / `llm_timeout` (타임아웃 초과)
- `turn_count` — 현재 저장된 히스토리 턴 수 (디버깅용)

### `POST /reset` — 특정 (player, npc) 히스토리 비우기

```json
// 요청
{ "player_id": "player_42", "npc_id": "blacksmith_bob" }
// 응답
{ "ok": true }
```

플레이어가 자리를 뜨거나 새 게임을 시작할 때 호출.

### `GET /health` — 서버 및 llama.cpp 연결 확인 (개발용)

서버 자체 상태와 llama.cpp 도달 가능 여부를 반환.

---

## 4. 내부 구성요소

각 유닛은 하나의 책임만 가지며 독립적으로 테스트 가능하다.

| 파일 | 책임 | 의존 |
|---|---|---|
| `main.py` | FastAPI 앱, 엔드포인트, 요청/응답 Pydantic 모델 | 전부 |
| `history.py` | `HistoryStore` 인터페이스 + `InMemoryHistoryStore`. `(player_id, npc_id)` 키, 최근 N턴 슬라이딩 윈도우. **← 나중에 SQLite 구현 교체 지점** | config |
| `llm_client.py` | llama.cpp 호출 (httpx). 타임아웃/연결오류를 잡아 결과로 반환 | config |
| `prompt.py` | `system_prompt + context + 히스토리 + message` → OpenAI `messages` 배열 조립 | 없음 (순수) |
| `config.py` | 설정값 로딩 (환경변수 / `.env`) | 없음 |

---

## 5. 설정값 (`config.py`)

| 값 | 기본 | 의미 |
|---|---|---|
| `LLAMA_BASE_URL` | `http://127.0.0.1:8080` | llama.cpp 주소 |
| `MAX_HISTORY_TURNS` | `10` | 유지할 최근 턴 수 (N) |
| `REQUEST_TIMEOUT` | `30` | llama.cpp 호출 타임아웃(초) |
| `LLAMA_MODEL` | `local` | OpenAI 호환 요청의 `model` 필드 값 |

> "턴"의 정의: user 발화 1 + assistant 응답 1 = 1턴. 슬라이딩 윈도우는 최근 `MAX_HISTORY_TURNS`턴을 유지.

---

## 6. 대화 흐름 (`/chat`)

1. 요청 파싱 → `(player_id, npc_id)`로 히스토리 조회
2. `prompt.py`가 messages 배열 조립: `[system(system_prompt+context)] + 최근 N턴 + [새 user message]`
3. `llm_client.py`가 llama.cpp 호출 (타임아웃 적용)
4. **성공** → assistant reply를 히스토리에 append (윈도우 초과 시 가장 오래된 턴 폐기), `ok:true` 반환
5. **실패** → 히스토리 **변경하지 않음**, `ok:false` + `error` 반환

> 실패 시 히스토리를 건드리지 않는 이유: 재시도 시 대화 일관성을 유지하고, 반쪽짜리 턴(user만 있고 assistant 없음)이 남지 않게 하기 위함.

---

## 7. 테스트 전략 (TDD)

| 대상 | 테스트 |
|---|---|
| `history.py` | append / 조회 / N턴 트리밍 / reset — 순수 로직, LLM 불필요 |
| `prompt.py` | messages 배열 조립 정확성 (system 합성, 턴 순서) |
| `llm_client.py` | llama.cpp를 mock — 성공 / 타임아웃 / 연결실패 3케이스 |
| `/chat` 통합 | llama.cpp mock — 정상 응답 + 실패 시 `ok:false` 검증 |
| `/reset` 통합 | 히스토리 비워지는지 검증 |

---

## 8. 향후 확장 지점 (범위 밖, 자리만 마련)

- **저장소 교체:** `HistoryStore` 인터페이스에 `SQLiteHistoryStore` 등 추가
- **히스토리 관리 고도화:** 슬라이딩 윈도우 → 토큰 기준 트리밍 또는 오래된 대화 요약
- **폴백 대사:** `ok:false`일 때 NPC가 얼버무리는 기본 대사 (UE5 또는 서버에서)
- **스트리밍:** 필요 시 SSE 엔드포인트 추가
