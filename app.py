"""AI 가계부 프론트 (Gradio)

실행: python app.py  →  http://localhost:7860
백엔드 연결은 api_client.py 참고 (환경변수 API_URL)
"""
import html
from datetime import date

import altair as alt
import gradio as gr
import pandas as pd

import api_client as api
from api_client import ApiError

PRIMARY = "#4F46E5"
PALETTE = [PRIMARY, "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#EC4899", "#8B5CF6", "#64748B"]


# ---------- 공통 ----------

def won(n):
    return f"{int(n):,}원"


def recent_months(n=12):
    y, m = date.today().year, date.today().month
    months = []
    for _ in range(n):
        months.append((f"{y}년 {m}월", f"{y}-{m:02d}"))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return months


MONTHS = recent_months()


def safe(fn, *args, default=None):
    """API 호출 실패 시 화면에 알림을 띄우고 기본값을 돌려줌"""
    try:
        return fn(*args)
    except ApiError as e:
        gr.Warning(str(e))
        return default


# ---------- 대시보드 ----------

def kpi_html(stats, budget):
    if stats is None:
        return '<div class="empty">백엔드에 연결되면 소비 현황이 여기에 표시돼요.</div>'
    total, count = stats.get("total", 0), stats.get("count", 0)
    if budget:
        remain, sub = won(budget - total), f"예산 {won(budget)} 중 {total / budget * 100:.0f}% 사용"
        bar = f'<div class="bar"><div style="width:{min(total / budget, 1) * 100:.0f}%"></div></div>'
    else:
        remain, sub, bar = "미설정", "아래에서 예산을 설정해 보세요", ""
    cards = [("총지출", won(total), f"{count}건"), ("남은 예산", remain, sub + bar)]
    body = "".join(
        f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div>'
        f'<div class="sub">{s}</div></div>'
        for label, value, s in cards
    )
    return f'<div class="kpi-row">{body}</div>'


def category_chart(by_category):
    df = pd.DataFrame(by_category.items(), columns=["카테고리", "금액"])
    cats = list(df["카테고리"])
    return alt.Chart(df, title="카테고리별 지출").mark_arc(innerRadius=60, cornerRadius=4).encode(
        theta="금액:Q",
        color=alt.Color("카테고리:N", legend=alt.Legend(orient="right", title=None),
                        scale=alt.Scale(domain=cats, range=PALETTE[:len(cats)] or PALETTE)),
        tooltip=["카테고리", alt.Tooltip("금액:Q", format=",")],
    ).properties(width="container", height=280)


def daily_chart(by_day):
    df = pd.DataFrame(by_day.items(), columns=["날짜", "금액"])
    df["날짜"] = pd.to_datetime(df["날짜"])
    return alt.Chart(df, title="일별 지출").mark_bar(
        color=PRIMARY, cornerRadiusTopLeft=4, cornerRadiusTopRight=4
    ).encode(
        x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%-d일", grid=False)),
        y=alt.Y("금액:Q", title=None, axis=alt.Axis(format="~s")),
        tooltip=[alt.Tooltip("날짜:T", format="%m월 %d일"), alt.Tooltip("금액:Q", format=",")],
    ).properties(width="container", height=280)


def load_dashboard(month):
    stats = safe(api.get_stats, month)
    budget = 0
    if stats is not None:
        budget = (safe(api.get_budget, month) or {}).get("amount", 0)
    has_data = bool(stats and stats.get("count"))
    return (
        kpi_html(stats, budget),
        category_chart(stats["by_category"]) if has_data else None,
        daily_chart(stats["by_day"]) if has_data else None,
        budget,
    )


def save_budget(month, amount):
    if safe(api.set_budget, month, int(amount or 0)) is not None:
        gr.Info("예산을 저장했어요")
    return load_dashboard(month)


# ---------- 내역 입력 ----------

def parse_text(text):
    if not text or not text.strip():
        gr.Warning("문장을 입력해 주세요")
        return [gr.skip()] * 4
    parsed = safe(api.parse_text, text.strip())
    if not parsed:
        return [gr.skip()] * 4
    gr.Info("내용을 확인하고 저장하세요")
    return (
        parsed.get("date") or date.today().isoformat(),
        parsed.get("item", ""),
        int(parsed.get("amount") or 0),
        parsed.get("category") or gr.skip(),
    )


def save_expense(d, item, amount, category, memo):
    try:
        date.fromisoformat((d or "").strip())
    except ValueError:
        gr.Warning("날짜는 2026-09-22 형식으로 입력해 주세요")
        return [gr.skip()] * 5
    if not (item or "").strip() or not amount or amount <= 0 or not category:
        gr.Warning("내용, 금액, 카테고리를 입력해 주세요")
        return [gr.skip()] * 5
    saved = safe(api.create_expense, {
        "date": d.strip(), "item": item.strip(), "amount": int(amount),
        "category": category, "memo": (memo or "").strip(),
    })
    if saved is None:
        return [gr.skip()] * 5
    gr.Info(f"저장했어요 · {item.strip()} {won(amount)}")
    return "", date.today().isoformat(), "", 0, ""


# ---------- 내역 목록 ----------

LIST_COLUMNS = ["날짜", "내용", "카테고리", "금액", "메모"]


def load_list(month, category):
    rows = safe(api.get_expenses, month, None if category in (None, "전체") else category)
    if not rows:
        summary = "내역이 없어요." if rows == [] else "내역을 불러오지 못했어요."
        return pd.DataFrame(columns=LIST_COLUMNS), summary, gr.update(choices=[], value=[])
    df = pd.DataFrame([{
        "날짜": r["date"], "내용": r["item"], "카테고리": r["category"],
        "금액": won(r["amount"]), "메모": r.get("memo", ""),
    } for r in rows])
    total = sum(r["amount"] for r in rows)
    choices = [(f"{r['date']} · {r['item']} · {won(r['amount'])}", r["id"]) for r in rows]
    return df, f"**{len(rows)}건** · 합계 **{won(total)}**", gr.update(choices=choices, value=[])


def delete_expenses(ids):
    if not ids:
        gr.Warning("삭제할 내역을 선택해 주세요")
        return
    done = sum(safe(api.delete_expense, i, default=False) is not False for i in ids)
    if done:
        gr.Info(f"{done}건을 삭제했어요")


# ---------- AI 상담 ----------

def add_user_message(message, chat_view):
    if not message or not message.strip():
        return gr.skip(), gr.skip()
    return "", chat_view + [{"role": "user", "content": message.strip()}]


def answer(chat_view, history, month):
    if not chat_view or chat_view[-1]["role"] != "user":
        return gr.skip(), gr.skip()
    question = chat_view[-1]["content"]
    if isinstance(question, list):  # Gradio가 content를 블록 목록으로 넘기는 경우
        question = " ".join(c.get("text", "") for c in question if isinstance(c, dict))
    res = safe(api.chat, question, month, history)
    if res is None:
        return chat_view[:-1], history
    reply = res.get("answer", "")
    return (
        chat_view + [{"role": "assistant", "content": reply}],
        history + [{"role": "user", "content": question}, {"role": "assistant", "content": reply}],
    )


def make_report(month):
    res = safe(api.get_report, month)
    return res.get("report", "") if res else "리포트를 만들지 못했어요."


# ---------- 카테고리 ----------

def load_categories():
    cats = safe(api.get_categories, default=[]) or []
    return gr.update(choices=cats, value=cats[0] if cats else None), gr.update(choices=["전체"] + cats, value="전체")


# ---------- 화면 ----------

CSS = """
.gradio-container { max-width: 1100px !important; margin: 0 auto; }
.app-header h1 { margin: 0; font-size: 28px; letter-spacing: -0.02em; }
.app-header p { margin: 6px 0 0; color: var(--body-text-color-subdued); }
.kpi-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.kpi { border: 1px solid var(--border-color-primary); border-radius: 14px; padding: 18px 20px;
       background: var(--block-background-fill); }
.kpi .label { color: var(--body-text-color-subdued); font-size: 14px; }
.kpi .value { font-size: 28px; font-weight: 700; margin-top: 4px; letter-spacing: -0.02em; }
.kpi .sub { color: var(--body-text-color-subdued); font-size: 13px; margin-top: 4px; }
.bar { height: 8px; background: var(--border-color-primary); border-radius: 99px; overflow: hidden; margin-top: 10px; }
.bar > div { height: 100%; background: #4F46E5; border-radius: 99px; }
.empty { padding: 28px; text-align: center; color: var(--body-text-color-subdued);
         border: 1px dashed var(--border-color-primary); border-radius: 14px; }
@media (max-width: 640px) { .kpi-row { grid-template-columns: 1fr; } }
"""

HEAD = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/pretendard.min.css">'

THEME = gr.themes.Soft(
    primary_hue="indigo",
    neutral_hue="slate",
    font=["Pretendard", "-apple-system", "sans-serif"],
)

with gr.Blocks(title="AI 가계부") as demo:
    gr.HTML(
        '<div class="app-header"><h1>AI 가계부</h1>'
        '<p>로컬 AI가 정리하는 내 소비 · 데이터는 외부로 나가지 않아요</p></div>'
    )
    with gr.Row(equal_height=True):
        month = gr.Dropdown(MONTHS, value=MONTHS[0][1], label="조회 월", scale=3)
        refresh_btn = gr.Button("새로고침", scale=1, size="lg")

    with gr.Tabs():
        with gr.Tab("대시보드"):
            kpi = gr.HTML()
            with gr.Row():
                cat_plot = gr.Plot(show_label=False)
                day_plot = gr.Plot(show_label=False)
            with gr.Accordion("예산 설정", open=False):
                with gr.Row(equal_height=True):
                    budget = gr.Number(label="이번 달 예산 (원)", precision=0, minimum=0, step=10000, scale=3)
                    budget_btn = gr.Button("저장", variant="primary", scale=1)

        with gr.Tab("내역 입력"):
            with gr.Group():
                gr.Markdown("### AI로 입력하기\n말하듯이 적으면 AI가 날짜·금액·카테고리를 채워드려요.")
                with gr.Row(equal_height=True):
                    ai_text = gr.Textbox(placeholder="예: 어제 스벅 5800원", show_label=False, scale=5)
                    parse_btn = gr.Button("분석", variant="primary", scale=1)
            gr.Markdown("### 내역 확인 · 저장")
            with gr.Row():
                f_date = gr.Textbox(label="날짜", value=date.today().isoformat(), placeholder="YYYY-MM-DD")
                f_amount = gr.Number(label="금액 (원)", value=0, precision=0, minimum=0, step=100)
            with gr.Row():
                f_item = gr.Textbox(label="내용", placeholder="예: 스타벅스")
                f_category = gr.Dropdown(label="카테고리", choices=[])
            f_memo = gr.Textbox(label="메모", placeholder="선택 사항")
            save_btn = gr.Button("저장하기", variant="primary", size="lg")

        with gr.Tab("내역 목록"):
            with gr.Row(equal_height=True):
                list_category = gr.Dropdown(label="카테고리", choices=["전체"], value="전체", scale=1)
                list_summary = gr.Markdown()
            table = gr.Dataframe(headers=LIST_COLUMNS, interactive=False, wrap=True, show_search="search")
            with gr.Accordion("내역 삭제", open=False):
                delete_pick = gr.Dropdown(label="삭제할 내역", choices=[], multiselect=True)
                delete_btn = gr.Button("선택한 내역 삭제", variant="stop")

        with gr.Tab("AI 상담"):
            with gr.Tabs():
                with gr.Tab("물어보기"):
                    chat_view = gr.Chatbot(
                        height=440, show_label=False,
                        placeholder="예: 카페에 얼마 썼어? / 지난달보다 많이 쓴 항목은?",
                    )
                    history = gr.State([])
                    with gr.Row(equal_height=True):
                        chat_input = gr.Textbox(placeholder="궁금한 걸 물어보세요", show_label=False, scale=5)
                        send_btn = gr.Button("보내기", variant="primary", scale=1)
                    clear_btn = gr.Button("대화 초기화", size="sm")
                with gr.Tab("월간 리포트"):
                    report_btn = gr.Button("리포트 만들기", variant="primary")
                    report = gr.Markdown()

    gr.Markdown(f"<small>백엔드: {html.escape(api.API_URL)}</small>")

    # ---------- 이벤트 ----------
    dash_out = [kpi, cat_plot, day_plot, budget]
    list_out = [table, list_summary, delete_pick]

    def refresh(m, c):
        return (*load_dashboard(m), *load_list(m, c))

    demo.load(load_categories, outputs=[f_category, list_category]).then(
        refresh, [month, list_category], dash_out + list_out)
    month.change(refresh, [month, list_category], dash_out + list_out)
    refresh_btn.click(load_categories, outputs=[f_category, list_category]).then(
        refresh, [month, list_category], dash_out + list_out)

    budget_btn.click(save_budget, [month, budget], dash_out)

    parse_btn.click(parse_text, ai_text, [f_date, f_item, f_amount, f_category])
    ai_text.submit(parse_text, ai_text, [f_date, f_item, f_amount, f_category])
    save_btn.click(save_expense, [f_date, f_item, f_amount, f_category, f_memo],
                   [ai_text, f_date, f_item, f_amount, f_memo]).then(
        refresh, [month, list_category], dash_out + list_out)

    list_category.change(load_list, [month, list_category], list_out)
    delete_btn.click(delete_expenses, delete_pick).then(
        refresh, [month, list_category], dash_out + list_out)

    for trigger in (chat_input.submit, send_btn.click):
        trigger(add_user_message, [chat_input, chat_view], [chat_input, chat_view]).then(
            answer, [chat_view, history, month], [chat_view, history])
    clear_btn.click(lambda: ([], []), outputs=[chat_view, history])
    report_btn.click(make_report, month, report)


if __name__ == "__main__":
    # share=True: 72시간 동안 외부에서 접속 가능한 공개 링크(https://xxxx.gradio.live) 생성
    demo.launch(theme=THEME, css=CSS, head=HEAD, share=True)
