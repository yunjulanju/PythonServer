# UE5 ↔ Relay Server 연동 가이드

UE5 NPC가 relay 서버를 통해 llama.cpp와 대화하는 방법을 설명합니다.

## 개요

- UE5 → relay 서버: `POST /chat`으로 NPC 페르소나(system prompt), 상황 컨텍스트, 플레이어 메시지를 전송
- relay 서버가 `(player_id, npc_id)`별 대화 히스토리를 메모리에 유지하고, OpenAI 형식 messages 배열을 조립해 llama.cpp에 전달
- 서버는 항상 HTTP 200으로 응답. 성공/실패는 `ok` 필드로 구분

기본 주소: `http://127.0.0.1:8000`

## 엔드포인트

### POST /chat

NPC와 한 턴 대화합니다.

요청 본문:

```json
{
  "player_id": "p1",
  "npc_id": "bob",
  "system_prompt": "You are a gruff blacksmith.",
  "context": "Player just returned your hammer.",
  "message": "Hello"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `player_id` | string | O | 플레이어 식별자 |
| `npc_id` | string | O | NPC 식별자 |
| `system_prompt` | string | O | NPC 페르소나 (system 메시지) |
| `context` | string | X | 이번 턴의 추가 상황 정보 (system에 덧붙음) |
| `message` | string | O | 플레이어가 보낸 메시지 |

응답 본문:

```json
{
  "reply": "What do you want?",
  "ok": true,
  "npc_id": "bob",
  "turn_count": 1,
  "error": null
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `reply` | string | NPC 응답 (실패 시 `""`) |
| `ok` | bool | 성공 여부 |
| `npc_id` | string | 요청한 NPC 식별자 |
| `turn_count` | int | 현재 저장된 대화 턴 수 |
| `error` | string \| null | 실패 시 에러 코드, 성공 시 `null` |

에러 코드:

| 코드 | 의미 |
|------|------|
| `llm_timeout` | llama.cpp 응답 시간 초과 |
| `llm_unavailable` | llama.cpp 연결 실패 또는 비정상 응답 |

실패 시에도 HTTP 상태는 200이며, 실패한 턴은 히스토리에 저장되지 않습니다.

### POST /reset

특정 `(player_id, npc_id)`의 대화 히스토리를 초기화합니다.

요청 본문:

```json
{ "player_id": "p1", "npc_id": "bob" }
```

응답:

```json
{ "ok": true }
```

### GET /health

서버와 llama.cpp 상태를 확인합니다.

응답:

```json
{ "server": true, "llama": true }
```

`llama`는 llama.cpp `/health`에 접근 가능하면 `true`, 아니면 `false`입니다.

## UE5 연동 시 유의사항

- 대화 히스토리는 서버가 관리하므로, UE5는 매 턴 전체 히스토리를 보낼 필요 없이 이번 턴 메시지만 보내면 됩니다.
- 히스토리는 인메모리이며 서버 재시작 시 사라집니다.
- 슬라이딩 윈도우로 최근 `MAX_HISTORY_TURNS`턴(기본 10)만 유지됩니다.
- 세션/대화를 새로 시작할 때 `/reset`을 호출하세요.
- 실패 응답도 200이므로, UE5 클라이언트는 HTTP 상태가 아니라 `ok` 필드로 성공을 판단해야 합니다.

## 서버 설정 (환경변수)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLAMA_BASE_URL` | `http://127.0.0.1:8080` | llama.cpp 주소 |
| `MAX_HISTORY_TURNS` | `10` | 유지할 최대 대화 턴 수 |
| `REQUEST_TIMEOUT` | `30.0` | llama.cpp 요청 타임아웃(초) |
| `LLAMA_MODEL` | `local` | 모델 이름 |
