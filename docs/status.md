# 현재 상황

## 서버 구현

`feat/relay-server` 브랜치에 5개 커밋으로 relay 서버 전체가 구현·커밋되어 있습니다.

| 모듈 | 역할 |
|------|------|
| `config.py` | 환경변수 기반 설정 로딩 |
| `history.py` | `(player_id, npc_id)`별 대화 히스토리 저장 (슬라이딩 윈도우) |
| `prompt.py` | 페르소나·컨텍스트·히스토리로 OpenAI messages 배열 조립 |
| `llm_client.py` | llama.cpp 호출, 타임아웃/에러 코드 매핑 |
| `main.py` | FastAPI 엔드포인트 `/chat`, `/reset`, `/health` |

각 모듈별 테스트는 `tests/`에 있습니다.

## 문서

- `docs/superpowers/plans/2026-07-16-ue5-llama-relay-server.md` — 구현 계획서
- `docs/superpowers/specs/2026-07-16-ue5-llama-relay-server-design.md` — 설계 스펙
- `docs/ue5-integration.md` — UE5 연동 가이드 (신규 작성)

## 남은 작업

- 리뷰 검증(테스트 실행)은 아직 수행하지 않았습니다.
