# study-portfolio

무무(mumu)의 학습 관제 센터 — 공부한 모든 것(PQC/암호학, 화이트햇스쿨, 논문, 삽질)을 기록하는
터미널 감성 정적 사이트.

## 구조

```
data/           모든 기록 (YAML / 마크다운) — 사람이 편집하는 곳
  weeks/        주간 로그 (YYYY-Www.yml)
  notes/        위키 노트 (마크다운, [[링크]] 문법)
  papers.yml    논문 리딩 노트
  projects.yml  프로젝트 (public: false 면 렌더링 제외)
  fails.yml     삽질/실패 기록
  skills.yml    스킬 트리
  me.yml        취향 코너
  site.yml      닉네임·컬러·연락처 등 전역 설정
scripts/build.py  data/ → docs/ 정적 사이트 생성기
templates/      주간 기록 템플릿
assets/         CSS/JS 원본 (빌드 시 docs/assets 로 복사)
docs/           빌드 결과물 = GitHub Pages 배포 대상 (직접 수정 금지)
```

## 노트 쓰기

**볼트 = `data/notes/`** — 옵시디언에서 이 폴더를 열면 저장하는 순간 이미 저장소 안이다.
옮기거나 복사하는 단계가 없다.

### 가장 쉬운 방법: 그냥 쓴다

옵시디언에서 새 노트를 만들고 **파일 이름만 잘 짓고 본문을 쓰면 끝.** 형식은 필요 없다.

- 제목 = 파일 이름 (`격자 기반 암호.md` → 사이트 제목 "격자 기반 암호")
- 날짜 = 마지막으로 저장한 날 (자동)
- 파일 이름에 공백·한글·괄호 다 써도 된다

### 형식을 갖추고 싶으면

`templates/note-template.md` 를 복사해서 내용만 채운다. 안 쓰는 항목은 지우면 된다.

```markdown
---
tags: [암호학]        ← 태그. 필요 없으면 이 3줄 통째로 지워도 됨
---

## 한 줄 요약
## 왜 필요한가
## 어떻게 동작하는가
## 예제
## 막혔던 곳       ← 삽질 기록. 포트폴리오에서 제일 값어치 있는 항목
## 참고
```

옵시디언 설정 → 템플릿 → 템플릿 폴더를 `../templates` 로 지정해두면
새 노트에서 단축키 한 번으로 이 틀을 넣을 수 있다.

### 쓰다 만 글 숨기기

frontmatter 에 `draft: true` 한 줄을 넣으면 사이트에 안 올라간다. 다 쓰고 그 줄을 지우면 공개된다.

```markdown
---
draft: true
---
```

### 사이트가 알아서 처리하는 것

| 옵시디언에서 | 사이트에서 |
|---|---|
| 파일명 `PE 파일 구조.md` | 주소 `wiki/pe-파일-구조.html` |
| `[[노트 이름]]` | 링크 (파일명·제목 아무거나 매칭) |
| `[[노트\|다르게 보이기]]` | 별칭 링크 |
| `[[노트#소제목]]` | 그 소제목으로 점프 |
| 이미지 붙여넣기 → `![[...]]` | 이미지 복사 + 삽입 |
| `> [!note] 제목` | 인용구 |
| 하위 폴더로 정리 | 그대로 동작 |
| 본문 맨 위 `# 제목` | 중복이라 자동 제거 |

`_` 나 `.` 으로 시작하는 폴더는 사이트가 무시한다. 단, **이 저장소는 공개이므로
파일 자체는 깃허브에 올라간다.** 남에게 보이면 안 되는 건 이 볼트에 두지 말 것.

## 사이트에 반영

### 방법 1 — GitHub 웹에서 (설치 불필요)

1. https://github.com/mumusecure/study-portfolio/tree/main/data/notes 열기
2. **Add file → Create new file**
3. 파일 이름에 `제목.md`, 아래 칸에 본문
4. **Commit changes**

1분쯤 뒤 사이트에 자동 반영된다. 폰에서도 된다.
저장소 아무 화면에서 `.` 키를 누르면 브라우저 안에서 VS Code 가 열린다(github.dev).

### 방법 2 — 로컬에서

```bash
./publish.sh              # 빌드 + 커밋 + 푸시
./publish.sh "메시지"      # 커밋 메시지 지정
```

첫 실행 때 빌드용 `.venv` 를 자동으로 만든다.

사실 `git push` 만 해도 GitHub 이 알아서 빌드·배포한다(`.github/workflows/deploy.yml`).
`publish.sh` 는 올리기 전에 로컬에서 확인하고 싶을 때 쓰면 된다.

## 주간 루틴 (15분 상한)

1. `cp templates/week-template.yml data/weeks/2026-W32.yml` — 이번 주차로 복사
2. 목록만 채운다. 문장 다듬지 않기. **15분 넘기지 않기**
3. `python3 scripts/build.py`
4. `git add -A && git commit -m "log: 2026-W32"` → push

커밋 히스토리가 곧 꾸준함의 증거다. 주 1회 이상 커밋이 목표.

## 커밋 전 공개 체크리스트

- [ ] 화이트햇스쿨 **내부 자료/교육 자료** 포함되지 않았는가?
- [ ] **비공개 취약점**, 제보 전 취약점 정보가 없는가?
- [ ] 타인의 **개인정보/연락처**가 없는가?
- [ ] 팀 프로젝트 내용은 팀원 동의를 받았는가? (애매하면 `public: false`)

## 배포 (GitHub Pages)

저장소 Settings → Pages → Source: `Deploy from a branch`, Branch: `main`, Folder: `/docs`

## 이스터에그

사이트 어딘가에 암호 퍼즐이 있다. 스포일러는 이 README에도 안 적는다.
