# hwp-parse-bench

HWP·HWPX 파서를 **원본 파일 그대로** 넣어 비교하는 공개 벤치마크입니다. RAG에 넣을 Markdown을 뽑을 때 어느 파서가 본문과 표를 얼마나 충실히 살리는지 수치로 보여 줍니다.

- 코퍼스(목록과 해시, 저장소에 넣을 수 있는 파일), 정답, 채점기, 어댑터, 실행별 집계와 문서별 점수를 공개합니다. 파서 원 출력은 크기 때문에 커밋하지 않으며, `uv run hwpbench run` 한 줄로 다시 낼 수 있습니다.
- 정답은 HWPX 원본 XML에서 **비교 대상 파서와 코드를 공유하지 않는** 참조 추출기로 만듭니다.
- 파서는 버전을 고정하고 프로세스마다 격리해서 돌립니다. macOS에서는 `sandbox-exec`로 네트워크도 막습니다(다른 OS는 컨테이너 안에서 돌리기를 권합니다. 실행 환경은 `meta.json`에 기록됩니다).

[English summary](#english)

## 결과

<!-- leaderboard:begin -->
실행 `20261113-012147` · macOS-26.6.2-arm64-arm-64bit-Mach-O · 시험 72건

| 파서 | 버전 | NID | TEDS 격자 | TEDS-S 격자 | TEDS 병합 없는 표 | TEDS 모든 표 | HWP 짝 NID | HWP 짝 TEDS 격자 | HWP 글자 F1 | 실패 | 시간(중앙) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| unhwp | 0.23.1 | 0.995 | 0.978 | 0.988 | 0.972 | 0.389 | 0.996 | 0.965 | 0.999 | 0% | 0.05s |
| rhwp-python | 0.8.1 | 0.983 | 0.990 | 1.000 | 0.972 | 0.996 | 0.956 | 0.992 | 0.976 | 0% | 0.10s |
| python-hwpx | 6.11.0 | 0.989 | 0.966 | 0.985 | 0.923 | 0.971 | 0.990 | 1.000 | 0.990 | 0% | 0.13s |
| kordoc | 4.24.47 | 0.999 | 0.910 | 0.910 | 0.969 | 0.611 | 0.999 | 0.855 | 0.995 | 0% | 0.14s |
| hwp-hwpx-parser | 1.0.0 | 0.986 | 0.883 | 0.884 | 0.998 | 0.958 | 0.999 | 0.819 | 0.989 | 0% | 0.06s |
| hwpforge | 0.19.1 | 0.998 | 0.786 | 0.789 | 0.991 | 0.945 | 0.996 | 0.701 | 0.996 | 0% | 0.06s |
| kordoc-gfm | 4.24.47 | 0.991 | 0.744 | 0.756 | 0.940 | 0.558 | 0.987 | 0.649 | 0.980 | 0% | 0.14s |
| gethwp | 1.1.1 | 0.894 | – | – | – | – | 0.948 | – | 0.969 | 0% | 0.04s |
| llama-index-readers-hwp | 0.6.0 | – | – | – | – | – | 0.948 | – | 0.969 | 0% | 0.59s |
| pyhwp | 0.1b15 | – | – | – | – | – | 0.998 | 1.000 | 0.999 | 0% | 0.16s |

- NID·TEDS 열: HWPX 원본 22건. 정답은 원본 XML에서 독립 추출했다. HWP 짝 열: 같은 문서의 HWP 7건(HWPX 정답 공유).
- HWP 글자 F1: 짝 HWPX가 없는 HWP 43건(법령 별표 등). 한컴 PDF의 글과 순서 무관 글자 F1로 비교한 약한 정답이다.
- TEDS 격자는 2행 2열 이상인 표만 본다. 보도자료 제목 상자 같은 1행·1열 꾸밈 틀을 글로 펴는 파서도 감점하지 않으려는 것이다. 모든 표를 본 값은 TEDS 모든 표 열에 있다. TEDS 병합 없는 표는 GFM처럼 병합 칸을 표현하지 못하는 출력과 공정하게 비교하려는 값이다.
- 정렬: NID와 TEDS 격자의 평균. 일반 텍스트만 내는 파서(표 지표 –)와 HWPX를 지원하지 않는 파서(pyhwp, llama-index)는 뒤에 둔다. pyhwp는 HWP 짝 열을 보면 된다. 실패(오류·시간 초과·빈 출력)는 0점으로 들어가고, 지원하지 않는 형식은 집계에서 뺀다. 제목 F1은 v0.1 정답에 개요 스타일 제목이 없어 싣지 않았다.
<!-- leaderboard:end -->

### 지표

| 지표 | 무엇을 재나 | 정의 |
|---|---|---|
| NID | 본문과 표 칸을 합친 전체 글이 얼마나 같은가 | 1 − Indel 거리 / (두 길이의 합). 표 칸은 행 순서로 펼친다. 각주는 위치가 파서마다 달라 뺀다. opendataloader-bench와 같은 정의 |
| TEDS | 표의 구조와 칸 내용 | Zhong et al. 2020의 트리 편집거리 유사도. 칸 글은 정규화 편집거리로 비교하고, 노드 수는 PubTabNet처럼 table 루트를 빼고 센다. 정답 표와 출력 표는 TEDS가 최대가 되게 짝짓고, 점수는 2·Σ짝 점수 / (정답 표 수 + 출력 표 수)다. 놓친 표와 남는 표는 0점 |
| TEDS-S | 표 구조만 | 칸 글을 무시한 TEDS |
| TEDS 격자 | 2행 2열 이상 표만 | 1행·1열짜리 꾸밈 틀(보도자료 제목 상자 등)을 빼고 본 TEDS. 꾸밈 틀을 글로 펴는 파서에 공정하게 하려는 하위 지표 |
| 제목 F1 | 개요 수준 제목 | 정답에 개요 스타일 제목이 있는 문서만 집계한다 |
| 글자 F1 | HWP 전용 문서의 글 보존 | 정답 HWPX가 없는 HWP(법령 별표 등)는 한컴이 만든 PDF의 글을 약한 정답으로 삼아 순서와 무관한 글자 F1만 잰다 |
| 실패 | 오류·시간 초과(60초)·빈 출력 비율 | 실패한 문서는 모든 지표가 0점으로 들어간다. 일반 텍스트만 내는 파서의 표 지표는 0점이 아니라 해당 없음(–)이다 |

### 비교 전 정규화

정답과 파서 출력에 같은 규칙을 씁니다(`src/hwpbench/model.py`, `normalize.py`).
- 유니코드 NFC, 공백류(전각 공백 포함)를 한 칸으로, 제로폭 문자 제거
- 사용자 정의 영역(PUA) 문자 제거: 한컴 고유 기호를 파서마다 그대로 두거나 다른 글자로 바꾸기 때문이다
- 가운뎃점 변형(‧ ∙ ・ ㆍ ᆞ)을 ·로 통일
- 전화번호는 `000-0000-0000`, 전자우편은 `x@x`로 가림. 보도자료 담당자 연락처를 공개 정답에 남기지 않기 위해서다. 양쪽을 같은 규칙으로 바꾸므로 점수에는 영향이 없다
- Markdown 강조 기호, 각주 참조 표시(`[^1]`) 제거. `[^1]: …` 정의는 각주 블록으로 본다
- 파이프 표는 머리 행보다 칸이 많은 행도 모든 칸을 살린다(GFM 규칙보다 너그럽게). HTML 표는 칸 안 문단·줄바꿈·표 안 표 사이를 띄운다

### 비교한 파서

`adapters/registry.json`에 버전, 라이선스, 선택한 옵션과 그 이유를 적어 두었습니다. 버전은 올라온 지 7일이 넘은 최신판으로 골랐습니다.

| 파서 | 언어 | 출력 | 비고 |
|---|---|---|---|
| kordoc / kordoc-gfm | TypeScript | Markdown (병합 칸 표는 HTML) / GFM 표만 | 같은 파서의 기본 출력과 GFM 출력 |
| unhwp | Rust (Python 바인딩) | Markdown + HTML 표 | |
| python-hwpx | Python | Markdown + HTML 표 | HWP는 내부에서 HWPX로 바꿔 읽음 |
| hwp-hwpx-parser | Python | Markdown (GFM 표) | 어댑터가 각주를 끝에 붙임 |
| hwpforge | Rust (Python 바인딩) | Markdown (GFM 표) | |
| rhwp-python | Rust (Python 바인딩) | Markdown (IR 렌더러) | `extract_text()`는 표 안 글을 내지 않아 IR 렌더러를 씀 |
| gethwp | Python | 일반 텍스트 | 표·제목 지표는 해당 없음(–) |
| llama-index-readers-hwp | Python | 일반 텍스트 | HWP만 지원 |
| pyhwp | Python (AGPL) | XHTML → 어댑터가 Markdown으로 변환 | HWP만 지원. 별도 프로세스로만 실행하고 코드는 포함하지 않음. **Markdown 변환은 이 저장소 코드라 점수에 어댑터 몫이 섞임** |

## 코퍼스

`corpus/manifest.jsonl`에 문서마다 출처, 내려받기 주소, SHA-256, 라이선스, 영역 태그를 적었습니다.

| 출처 | 문서 | 형식 | 라이선스 | 저장소에 포함 |
|---|---|---|---|---|
| 국가법령정보센터 법령 별표·서식 | 42 | HWP (+PDF) | 저작권법 제7조(보호받지 못하는 저작물) | 포함 (`corpus/files/`) |
| 정책브리핑 보도자료 | 23 | HWPX 22 (이 중 HWP 짝 7), HWP만 1. PDF 21 | 공공누리 제1유형(출처표시), "텍스트에 한하여" | 미포함. `hwpbench fetch`가 원 출처에서 받아 해시를 확인함 |

- HWP 짝은 HWP 본문 글과 HWPX 본문 글의 유사도가 0.98 이상인 것만 인정합니다. 부처가 같은 이름으로 올렸어도 내용이 다른 경우가 있었습니다.
- 법제처의 "HWPX 내려받기"는 HWP와 바이트가 같은 파일이라 쓰지 않았습니다.

## 정답

- **구조 트랙** (`truth/<id>.json`, `.md`): HWPX의 `Contents/section*.xml`을 lxml로 직접 읽습니다.
  - 넣는 것: 문단, 표(병합 칸 포함, 표 안 표는 칸 글로), 글상자(앵커 위치), 각주·미주(끝에 별도 블록)
  - 빼는 것: 머리말·꼬리말·쪽 번호·수식
  - 제목은 개요(OUTLINE) 문단 모양만 인정합니다.
- **텍스트 트랙** (`truth/<id>.txt`): 한컴이 만든 PDF에서 뽑은 글입니다.
- 정답마다 `status`(`auto` | `reviewed`)가 있습니다. v0.1의 정답은 모두 `auto`(사람 검수 전)이고, 순위표도 `auto` 정답으로 냈습니다. 사람이 검수한 정답만으로 낸 점수는 `results/<run>/summary.json`의 `structure_reviewed`에 있습니다.

## 실행

```bash
uv sync
uv run hwpbench fetch        # 저장소에 없는 정책브리핑 파일을 받고 해시 확인
uv run hwpbench truth        # 정답 다시 만들기 (검수된 정답은 건너뜀)
uv run hwpbench run          # 어댑터 준비 → 측정 실행 → 채점 → README 순위표 갱신
uv run hwpbench run --adapters kordoc,unhwp --only kr-156757806
```

- Node 20 이상(kordoc), uv가 필요합니다. uv가 관리하는 Python만 쓰도록 설정해 두었습니다(시스템 Python의 ssl 누락 같은 기기 차이 방지).
- 어댑터 버전은 각 스크립트의 PEP 723 머리말과 `adapters/kordoc/package-lock.json`에 고정돼 있고, Dependabot 대상이 아니라 직접 올립니다.
- 측정 실행은 macOS에서 `sandbox-exec`로 네트워크를 막습니다. 다른 OS에서는 컨테이너(`--network none`) 안에서 돌리기를 권합니다.
- 결과는 `results/<run-id>/`에 남습니다. 원 출력(`raw/`), 실행 기록(`runs.jsonl`), 문서별 점수(`scores.jsonl`), 집계(`summary.json`), 실행 환경(`meta.json`)입니다.

## 한계

- 코퍼스가 작고(65문서) 공문서에 치우쳐 있습니다. 다단, 각주, 배포용·암호 문서, HWP 3.x는 아직 없습니다.
- 대부분의 정답은 자동 추출(`auto`)입니다. 참조 추출기의 오류가 모든 파서의 점수에 같은 방향으로 들어갑니다.
- 공문서는 개요 스타일 대신 □○- 기호로 위계를 나타내는 경우가 많아, 제목 지표를 집계할 수 있는 문서가 적습니다.
- RAG 하류 지표(질문-정답 쌍으로 잰 검색 적중률, 청크 메타데이터)는 아직 없습니다.
- 정답은 표 안의 표를 바깥 칸의 글로 펼칩니다. 중첩 표를 별도 표로 꺼내는 출력(kordoc-gfm 등)은 표 개수가 달라 TEDS에서 감점됩니다.
- 참조 추출기는 아직 변경 추적(지운 글), 덧말, 글자 겹침을 다루지 않습니다. v0.1 코퍼스에는 이런 요소가 없습니다.

## 고지

- 본 제품은 한글과컴퓨터의 한/글 문서 파일(.hwp) 공개 문서를 참고하여 개발하였습니다.
- 한글, 한컴, HWP, HWPX는 ㈜한글과컴퓨터의 등록상표입니다. 이 프로젝트는 한글과컴퓨터와 제휴 관계가 없습니다.
- 정책브리핑 보도자료는 각 부처가 공공누리 제1유형으로 공개한 저작물입니다. 출처는 `corpus/manifest.jsonl`의 `publisher`·`source_page`에 있습니다.
- 코드는 MIT, 정답·주석 파일(`truth/`)은 CC BY 4.0입니다. 다만 정답에 담긴 글 자체는 원저작물 조건(저작권법 제7조, 공공누리 제1유형 텍스트)을 따릅니다. 코퍼스 파일은 각 문서의 원래 조건을 따릅니다.

## English

hwp-parse-bench is an open, reproducible benchmark for parsers that turn Korean HWP/HWPX word-processor files into Markdown for RAG. It feeds the original files (not PDFs or page images) to each parser, pinned and network-isolated, and scores text fidelity (NID), table structure and content (TEDS / TEDS-S), and outline headings against ground truth extracted directly from HWPX XML by an independent reference extractor. The corpus (public-domain statute annexes bundled; government press releases fetched by hash), truth, scorer, adapters, per-run summaries and per-document scores are published; raw parser outputs are not committed but can be regenerated with one command.
