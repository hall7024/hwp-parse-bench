# 어댑터

파서 하나에 어댑터 하나를 둔다. 어댑터는 HWP·HWPX 파일 하나를 받아 UTF-8 텍스트 파일 하나(Markdown 또는 일반 텍스트)를 쓴다. 목록과 설정 이유는 `registry.json`에 있다.

## 규약

- 실행: `<registry의 command> <입력 파일> <출력 파일>`
  - Python: `uv run --script adapters/<name>.py <입력> <출력>`
  - kordoc: `node adapters/kordoc/run.mjs [--table-format=gfm] <입력> <출력>`
- 성공하면 0으로 끝난다. 실패하면 0이 아닌 코드로 끝내고 stderr에 한 줄을 쓴다.
- Python 어댑터는 hwpbench를 import하지 않는 독립 스크립트다. PEP 723 머리말에 Python 버전과 의존성을 정확한 버전으로 적고, 옆의 `<name>.py.lock`이 간접 의존성까지 고정한다.
- 버전은 저장소 규칙(`exclude-newer = "7 days"`)에 맞춰 올라온 지 일주일이 넘은 것만 쓴다. 각 스크립트의 `exclude-newer`는 날짜로 박아 두었다.
- 파서마다 가장 좋은 Markdown이 나오는 옵션을 쓴다. 병합 칸을 HTML 표로 낼 수 있으면 그 옵션을 켠다. 고른 이유는 `registry.json`의 `notes`에 적는다.
- 파일 이름이 패키지 이름과 같아도(`unhwp.py`, `hwpforge.py`, `gethwp.py`) 스크립트가 맨 앞에서 자기 폴더를 import 경로에서 빼므로 패키지를 가리지 않는다.

## kordoc

```bash
cd adapters/kordoc && npm ci   # package-lock 고정. .npmrc가 install script와 optional 의존성을 막는다
```

`run.mjs`가 `KORDOC_OFFLINE=1`을 켜고 OCR을 끈다.

## 네트워크

macOS에서는 `sandbox-exec`로 네트워크를 막고 돌릴 수 있다. 환경을 한 번 만든 뒤에는 `uv run --offline`을 함께 쓴다.

```bash
sandbox-exec -p '(version 1)(allow default)(deny network*)' uv run --offline --script adapters/unhwp.py in.hwpx out.md
```

10개 어댑터 모두 이 방식으로 네트워크 없이 돌아가는 것을 확인했다(2026-11-13).

## 라이선스

어댑터 코드는 저장소 라이선스를 따른다. pyhwp(AGPL-3.0)는 import하지 않고 `hwp5html` 명령을 별도 프로세스로 실행하며, 저장소에 pyhwp 코드를 넣지 않는다.
