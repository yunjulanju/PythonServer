# 파이썬 서버 실행 방법

이 프로젝트는 FastAPI relay 서버입니다. `python main.py`로는 실행되지 않습니다
(`main.py`에는 실행 코드 없이 `app` 객체만 정의되어 있음). **uvicorn**으로 띄워야 합니다.

## 요약

```powershell
cd C:\Work\PythonServer
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

→ `http://127.0.0.1:8000` 에서 서버가 뜹니다.

---

## 단계별 설명

### 1. 프로젝트 폴더로 이동

```powershell
cd C:\Work\PythonServer
```

### 2. 가상환경 활성화

```powershell
.\.venv\Scripts\Activate.ps1
```

- 활성화되면 프롬프트 앞에 `(.venv)` 가 붙습니다.
- PowerShell에서 실행 정책 오류가 나면 한 번만 아래 실행:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```

### 3. 서버 실행

```powershell
uvicorn main:app --reload
```

- `main:app` = `main.py` 파일 안의 `app` 객체를 의미.
- `--reload` = 코드를 수정하면 서버가 자동으로 다시 로드됨 (개발용).
- 기본 주소: `http://127.0.0.1:8000`

포트를 바꾸고 싶으면:

```powershell
uvicorn main:app --reload --port 9000
```

### 4. 종료

터미널에서 `Ctrl + C`

---

## llama 없이도 켜지나요? → 네

파이썬 서버 자체는 llama가 꺼져 있어도 **정상적으로 실행됩니다.**
llama가 필요한 건 실제 대화(`/chat`)를 처리할 때뿐입니다.

| 기능 | llama 필요 여부 |
|------|-----------------|
| 서버 실행 (`uvicorn ...`) | ❌ 불필요 |
| `/docs` (API 문서 페이지) | ❌ 불필요 |
| `/health` (상태 확인) | ❌ 불필요 (llama 연결 여부만 알려줌) |
| `/reset` (히스토리 초기화) | ❌ 불필요 |
| `/chat` (실제 대화) | ✅ **필요** — 꺼져 있으면 에러 반환 |

llama가 꺼진 상태에서 `/chat`을 호출하면 서버가 죽지는 않고,
`{"ok": false, "error": "llm_unavailable"}` 같은 응답을 돌려줍니다.

---

## 잘 떴는지 확인하는 법

브라우저에서 아래 주소를 엽니다.

- **API 문서 (테스트 UI):** http://127.0.0.1:8000/docs
- **상태 확인:** http://127.0.0.1:8000/health
  - 응답 예시: `{"server": true, "llama": true}`
  - `"llama": true` → llama 서버(8080 포트)까지 정상 연결됨
  - `"llama": false` → 파이썬 서버는 떴지만 llama는 아직 연결 안 됨

---

## llama 서버 주소가 다를 때

기본값은 `http://127.0.0.1:8080` 입니다 (`config.py`).
llama를 다른 포트/주소로 켰다면, 서버 실행 **전에** 환경변수로 지정하세요.

```powershell
$env:LLAMA_BASE_URL = "http://127.0.0.1:8080"
uvicorn main:app --reload
```

조정 가능한 환경변수 (모두 선택 사항):

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `LLAMA_BASE_URL` | `http://127.0.0.1:8080` | llama.cpp 서버 주소 |
| `MAX_HISTORY_TURNS` | `10` | 유지할 대화 턴 수 |
| `REQUEST_TIMEOUT` | `30` | llama 요청 타임아웃(초) |
| `LLAMA_MODEL` | `local` | 모델 이름 |
