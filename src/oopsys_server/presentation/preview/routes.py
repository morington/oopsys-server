import asyncio
import json
import random

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from starlette.responses import HTMLResponse

from oopsys_server.presentation.preview.fixtures import PAGES, SCENARIOS, _account, build_context
from oopsys_server.presentation.web.templating import render

router = APIRouter(tags=["preview"])

@router.get("/__preview", response_class=HTMLResponse)
async def preview_index(request: Request) -> HTMLResponse:
    rows = []
    for page in PAGES:
        links = " · ".join(f'<a href="/__preview/{page}?scenario={s}">{s}</a>' for s in SCENARIOS)
        rows.append(f"<tr><td><strong>{page}</strong></td><td>{links}</td></tr>")
    body = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">\n    <title>oopsys · preview</title><link rel="stylesheet" href="/static/app.css"></head>\n    <body><div class="content" style="max-width:760px;margin:0 auto">\n    <div class="brand" style="font-size:20px;padding:18px 0"><span class="dot"></span> oopsys · превью дизайна</div>\n    <div class="alert info">Режим разработки: страницы рендерятся на мок-данных без БД, NATS и авторизации.</div>\n    <table class="table"><thead><tr><th>Страница</th><th>Сценарии</th></tr></thead>\n    <tbody>{''.join(rows)}</tbody></table>\n    </div></body></html>"""
    return HTMLResponse(body)

@router.get("/__preview/{page}", response_class=HTMLResponse)
async def preview_page(request: Request, page: str, scenario: str="default") -> HTMLResponse:
    if page not in PAGES:
        return HTMLResponse(f"unknown page '{page}'", status_code=404)
    request.state.account = _account()
    context = build_context(page, scenario)
    return render(request, PAGES[page], context)

@router.get("/web/stream")
async def fake_stream(request: Request) -> EventSourceResponse:

    async def gen():
        titles = ["ValueError в cryptobot", "TimeoutError в payments", "Агент восстановлен"]
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(4)
            yield {"event": "metric", "data": json.dumps({"cpu_percent": random.randint(10, 95)})}
            await asyncio.sleep(4)
            yield {"event": "notification", "data": json.dumps({"title": random.choice(titles), "body": "preview", "severity": random.choice(["error", "critical"])}, ensure_ascii=False)}
    return EventSourceResponse(gen())
