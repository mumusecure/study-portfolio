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
