# AI 가계부 프론트엔드

Gradio 기반 웹 화면. AI 기능은 백엔드([BackEnd](https://github.com/AI-Project-5week/BackEnd))가 로컬 LLM(Ollama, exaone3.5:2.4b)으로 처리합니다.

## 실행

```
pip install -r requirements.txt
set API_URL=http://<백엔드 IP>:8000
python app.py
```

- 로컬 주소: http://127.0.0.1:7860
- 공개 링크: 실행 시 터미널에 `https://xxxx.gradio.live` 주소가 함께 표시됨 (72시간 유지)
- `API_URL`을 지정하지 않으면 `http://localhost:8000`에 연결

## 화면

| 탭 | 기능 |
| --- | --- |
| 대시보드 | 총지출, 남은 예산, 카테고리별·일별 차트, 예산 설정 |
| 내역 입력 | AI로 입력하기("어제 스벅 5800원"), 직접 입력 후 저장 |
| 내역 목록 | 카테고리 필터, 검색, 삭제 |
| AI 상담 | 소비 상담 채팅, 월간 리포트 |

## 파일 구성

| 파일 | 역할 |
| --- | --- |
| `app.py` | Gradio 화면 |
| `api_client.py` | 백엔드 API 호출 (모든 요청이 여기에 모여 있음) |
| `API_명세서.md` | 백엔드와 합의한 API 명세 |
