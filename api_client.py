"""백엔드 API 연결 모듈

화면(app.py)은 이 파일의 함수만 호출합니다.
백엔드가 준비되면 API_URL과 아래 경로/응답 형식만 맞추면 됩니다.

서버 주소는 환경변수 API_URL로 바꿀 수 있습니다.
    (cmd)        set API_URL=http://192.168.0.10:8000
    (PowerShell) $env:API_URL="http://192.168.0.10:8000"
"""
import os

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 120  # LLM 응답이 느릴 수 있어 넉넉하게


class ApiError(Exception):
    """화면에 그대로 보여줄 수 있는 에러 메시지"""


def _request(method, path, **kwargs):
    try:
        res = requests.request(method, API_URL + path, timeout=TIMEOUT, **kwargs)
        res.raise_for_status()
        return res.json() if res.content else None
    except requests.ConnectionError:
        raise ApiError(f"백엔드 서버({API_URL})에 연결할 수 없어요.")
    except requests.Timeout:
        raise ApiError("서버 응답이 너무 오래 걸려요. 잠시 후 다시 시도해 주세요.")
    except requests.HTTPError as e:
        raise ApiError(f"서버 오류가 발생했어요. ({e.response.status_code})")
    except ValueError:
        raise ApiError("서버 응답 형식이 올바르지 않아요.")


# ---------- 기본 정보 ----------

def get_categories():
    """GET /categories
    응답: ["식비", "카페", "교통", ...]
    """
    return _request("GET", "/categories")


def get_budget(month):
    """GET /budget?month=2026-09
    응답: {"month": "2026-09", "amount": 500000}   (미설정이면 amount: 0)
    """
    return _request("GET", "/budget", params={"month": month})


def set_budget(month, amount):
    """PUT /budget
    요청: {"month": "2026-09", "amount": 500000}
    """
    return _request("PUT", "/budget", json={"month": month, "amount": amount})


# ---------- 지출 내역 ----------

def get_expenses(month, category=None):
    """GET /expenses?month=2026-09&category=카페   (category 생략 시 전체)
    응답: [{"id": 1, "date": "2026-09-22", "item": "스타벅스",
            "amount": 5800, "category": "카페", "memo": ""}, ...]
    """
    params = {"month": month}
    if category:
        params["category"] = category
    return _request("GET", "/expenses", params=params)


def create_expense(expense):
    """POST /expenses
    요청: {"date": "2026-09-22", "item": "스타벅스", "amount": 5800,
           "category": "카페", "memo": ""}
    """
    return _request("POST", "/expenses", json=expense)


def delete_expense(expense_id):
    """DELETE /expenses/{id}"""
    return _request("DELETE", f"/expenses/{expense_id}")


def get_stats(month):
    """GET /stats?month=2026-09
    응답: {"total": 185000, "count": 14,
           "by_category": {"식비": 84200, "카페": 14100, ...},
           "by_day": {"2026-09-01": 12000, ...}}
    """
    return _request("GET", "/stats", params={"month": month})


# ---------- AI ----------

def parse_text(text):
    """POST /parse   자연어 문장 → 지출 항목
    요청: {"text": "어제 스벅 5800원"}
    응답: {"date": "2026-09-22", "item": "스타벅스", "amount": 5800, "category": "카페"}
    """
    return _request("POST", "/parse", json={"text": text})


def chat(message, month, history):
    """POST /chat   month = 사이드바에서 선택한 월 (이 달 데이터 기준으로 답변)
    요청: {"message": "카페에 얼마 썼어?", "month": "2026-09",
           "history": [{"role": "user"|"assistant", "content": "..."}, ...]}
    응답: {"answer": "..."}
    """
    return _request("POST", "/chat", json={"message": message, "month": month, "history": history})


def get_report(month):
    """GET /report?month=2026-09
    응답: {"report": "마크다운 형식의 리포트 본문"}
    """
    return _request("GET", "/report", params={"month": month})
