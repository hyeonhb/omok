# Omok AI

학교 과제용 19x19 오목 인공지능 프로젝트입니다. 규칙을 지키는 엔진, 3초 이내 응답, 탐색 기반 AI, CLI 데모, pytest 테스트를 포함합니다.

## 프로젝트 구조

```text
omok_ai/
├─ README.md
├─ requirements.txt
├─ main.py
├─ omok/
│  ├─ constants.py
│  ├─ board.py
│  ├─ rules.py
│  ├─ patterns.py
│  ├─ evaluator.py
│  ├─ move_generator.py
│  ├─ search.py
│  ├─ threat_search.py
│  └─ ai.py
└─ tests/
   ├─ test_rules.py
   ├─ test_win.py
   ├─ test_forbidden.py
   └─ test_ai_basic.py
```

## 실행 방법

```bash
python main.py
```

실행하면 GUI가 열립니다. 지정 금수 좌표 3개와 AI 색상을 선택한 뒤 게임을 시작할 수 있습니다.

```text
금수 좌표 3개: 3 3, 10 12, 15 7
AI 색상: 흑 또는 백
```

사람 차례에는 보드 클릭으로 칸을 선택하고, `착수` 버튼을 눌러야 실제로 돌이 놓입니다. 흑돌과 백돌은 문자 대신 원형 돌로 표시됩니다.

## 테스트 방법

```bash
pip install -r requirements.txt
pytest
```

## 좌표계

외부 API와 CLI는 1-based 좌표를 사용합니다.

```text
행: 1~19
열: 1~19
좌측하단: (1, 1)
우측상단: (19, 19)
중앙: (10, 10)
```

내부 보드는 Python 배열에 맞춰 0-based 좌표를 사용합니다. 변환 함수는 `omok.constants`에 분리되어 있습니다.

```python
to_internal((1, 1))    # (18, 0)
to_external((18, 0))   # (1, 1)
to_internal((10, 10))  # (9, 9)
to_external((9, 9))   # (10, 10)
```

## 구현된 규칙

- 보드는 19x19입니다.
- AI 기본 색상은 흑입니다.
- 흑의 첫 수는 가능한 경우 중앙 `(10, 10)`입니다.
- 게임 시작 전 지정 금수 좌표를 설정할 수 있고, 흑/백 모두 둘 수 없습니다.
- 지정 금수 칸은 후보 생성, 합법 수 판정, 패턴 분석, 탐색에서 벽처럼 취급합니다.
- 쌍삼과 쌍사는 불법 수입니다.
- 장목 금지는 없습니다. 5개 이상 연결되면 승리입니다.
- 합법성 검사에서는 승리 판정을 먼저 수행하므로, 5목 이상을 완성하는 수는 쌍삼/쌍사처럼 보여도 허용됩니다.

## AI 전략 요약

`OmokAI.choose_move()`는 다음 순서로 수를 고릅니다.

1. 흑 첫 수 중앙 착수
2. 즉시 승리 수 탐색
3. 상대 즉시 승리 방어
4. 짧은 위협 기반 공격 탐색
5. 짧은 위협 기반 방어 탐색
6. Iterative Deepening Negamax + Alpha-Beta
7. 휴리스틱 fallback

후보 수는 전체 빈 칸이 아니라 기존 돌 주변 2칸 이내를 우선 사용합니다. 초반에는 중앙 주변 후보를 먼저 고려합니다.

## 3초 제한 대응

- `time_limit=3.0`이 들어오면 내부 deadline은 최대 `start + 2.75`초로 잡습니다.
- 탐색 시작 전에 합법 fallback 수를 확보합니다.
- iterative deepening은 depth 하나가 끝날 때마다 best move를 갱신합니다.
- 모든 재귀 탐색은 deadline을 확인하고, 시간이 부족하면 `TimeoutError`로 중단합니다.
- 예외가 발생해도 fallback 또는 보드 전체 첫 합법 수를 반환합니다.

## 한계와 개선 가능성

- 패턴 평가는 실전용 고성능 엔진보다 단순한 휴리스틱 기반입니다.
- Threat Search는 짧은 강제 수열만 확인합니다.
- Transposition Table은 기본 구조가 구현되어 있으나, 엔트리 교체 정책과 저장 범위 최적화는 단순합니다.
- 더 강한 AI를 위해서는 정교한 금수 판정, 패턴 중복 제거, killer move/history heuristic, opening book을 추가할 수 있습니다.
