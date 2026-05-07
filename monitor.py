#!/usr/bin/env python3
"""
Sultan Crash Monitor v3 - Con comandos interactivos
Responde a: /estado, /historial, /resumen
"""

import asyncio
import json
import logging
import aiohttp
import websockets

TELEGRAM_TOKEN = "8338023730:AAFSmB04tSjxkg8vn1wj1sPON0mquz-ORvQ"
CHAT_ID = "7706931467"
WS_URL = "wss://crashdata.hashesgames.com/socket.io/?EIO=4&transport=websocket"

TARGETS = [
    {"key": "x25",  "mult": 25,  "alert": 99.0, "urgent": 99.6},
    {"key": "x50",  "mult": 50,  "alert": 99.0, "urgent": 99.6},
    {"key": "x100", "mult": 100, "alert": 99.0, "urgent": 99.6},
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

history = []
MAX_HISTORY = 1000
last_alerts = {}
last_update_id = 0


def calc_prob(multiplier, results):
    misses = 0
    for r in reversed(results):
        if r >= multiplier:
            break
        misses += 1
    if misses == 0:
        return 0.0, 0
    base_prob = 1.0 / multiplier
    cumulative = 1.0 - (1.0 - base_prob) ** misses
    return round(cumulative * 100, 2), misses


async def send_telegram(session, msg, priority=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_notification": not priority}
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                log.info(f"Enviado: {msg[:60]}")
    except Exception as e:
        log.error(f"Error Telegram: {e}")


async def check_alerts(session, crashed_at):
    for t in TARGETS:
        mult = t["mult"]
        key = t["key"]
        prob, misses = calc_prob(mult, history)

        if prob >= t["urgent"]:
            alert_key = f"{key}_urgent_{misses // 5}"
            if alert_key not in last_alerts:
                msg = (
                    f"🚨🔥 <b>URGENTE - {key.upper()}!</b>\n\n"
                    f"📊 Probabilidad: <b>{prob}%</b>\n"
                    f"🎯 Objetivo: ×{mult}\n"
                    f"🔢 Rondas sin salir: <b>{misses}</b>\n"
                    f"📉 Último crash: ×{crashed_at}\n\n"
                    f"⚡ <b>¡MÁXIMA OPORTUNIDAD!</b>"
                )
                await send_telegram(session, msg, priority=True)
                last_alerts[alert_key] = True
                last_alerts.pop(f"{key}_alert_{misses // 5}", None)

        elif prob >= t["alert"]:
            alert_key = f"{key}_alert_{misses // 5}"
            if alert_key not in last_alerts:
                msg = (
                    f"⚠️ <b>ALERTA - {key.upper()}</b>\n\n"
                    f"📊 Probabilidad: <b>{prob}%</b>\n"
                    f"🎯 Objetivo: ×{mult}\n"
                    f"🔢 Rondas sin salir: <b>{misses}</b>\n"
                    f"📉 Último crash: ×{crashed_at}\n\n"
                    f"👀 Probabilidad muy alta"
                )
                await send_telegram(session, msg, priority=True)
                last_alerts[alert_key] = True
        else:
            for k in list(last_alerts.keys()):
                if k.startswith(key):
                    last_alerts.pop(k)


async def cmd_estado(session):
    if not history:
        await send_telegram(session, "⏳ Todavía no hay datos. Esperá unos minutos.")
        return
    lines = ["📊 <b>Estado actual</b>\n"]
    for t in TARGETS:
        prob, misses = calc_prob(t["mult"], history)
        if prob >= 99.6:
            emoji = "🔴"
        elif prob >= 99.0:
            emoji = "🟡"
        elif prob >= 90:
            emoji = "🟠"
        else:
            emoji = "🟢"
        lines.append(f"{emoji} ×{t['mult']}: <b>{prob}%</b> ({misses} rondas sin salir)")
    lines.append(f"\n📉 Último crash: ×{history[-1]}")
    lines.append(f"📈 Total rondas: {len(history)}")
    await send_telegram(session, "\n".join(lines))


async def cmd_historial(session):
    if not history:
        await send_telegram(session, "⏳ Todavía no hay datos.")
        return
    ultimos = history[-15:]
    lineas = ["📋 <b>Últimos 15 resultados:</b>\n"]
    for i, val in enumerate(reversed(ultimos), 1):
        if val >= 100:
            emoji = "🔥"
        elif val >= 50:
            emoji = "💥"
        elif val >= 25:
            emoji = "⭐"
        elif val >= 10:
            emoji = "✅"
        else:
            emoji = "💀"
        lineas.append(f"{emoji} ×{val}")
    await send_telegram(session, "\n".join(lineas))


async def cmd_resumen(session):
    if len(history) < 10:
        await send_telegram(session, "⏳ Necesito más datos. Esperá un rato.")
        return

    total = len(history)
    lines = [f"📊 <b>Resumen completo</b> ({total} rondas)\n"]

    for t in TARGETS:
        mult = t["mult"]
        count = sum(1 for r in history if r >= mult)
        pct_real = round(count / total * 100, 1)
        pct_esperado = round(1 / mult * 100, 1)
        prob, misses = calc_prob(mult, history)

        if pct_real < pct_esperado * 0.7:
            estado = "⚠️ Sale MENOS de lo esperado"
        elif pct_real > pct_esperado * 1.3:
            estado = "📈 Sale MÁS de lo esperado"
        else:
            estado = "✅ Normal"

        lines.append(
            f"🎯 <b>×{mult}</b>\n"
            f"   Real: {pct_real}% | Esperado: {pct_esperado}%\n"
            f"   {estado}\n"
            f"   Prob. acumulada ahora: {prob}%\n"
        )

    # Mejor y peor racha
    max_val = max(history)
    min_val = min(history)
    lines.append(f"🏆 Máximo: ×{max_val}")
    lines.append(f"💀 Mínimo: ×{min_val}")

    await send_telegram(session, "\n".join(lines))


async def check_commands(session):
    """Revisa si el usuario mandó algún comando al bot"""
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 1}
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    text = msg.get("text", "").lower().strip()

                    if text == "/estado":
                        await cmd_estado(session)
                    elif text == "/historial":
                        await cmd_historial(session)
                    elif text == "/resumen":
                        await cmd_resumen(session)
                    elif text == "/ayuda" or text == "/help":
                        ayuda = (
                            "🤖 <b>Comandos disponibles:</b>\n\n"
                            "/estado — Ver probabilidades actuales\n"
                            "/historial — Últimos 15 resultados\n"
                            "/resumen — Análisis completo\n"
                            "/ayuda — Esta ayuda"
                        )
                        await send_telegram(session, ayuda)
    except:
        pass


async def poll_commands(session):
    """Revisa comandos cada 3 segundos"""
    while True:
        await check_commands(session)
        await asyncio.sleep(3)


async def status_update(session):
    await asyncio.sleep(3600)
    while True:
        if history:
            lines = ["📊 <b>Resumen horario</b>\n"]
            for t in TARGETS:
                prob, misses = calc_prob(t["mult"], history)
                if prob >= 99.6:
                    emoji = "🔴"
                elif prob >= 99.0:
                    emoji = "🟡"
                elif prob >= 90:
                    emoji = "🟠"
                else:
                    emoji = "🟢"
                lines.append(f"{emoji} ×{t['mult']}: {prob}% ({misses} rondas)")
            lines.append(f"\n📈 Total rondas: {len(history)}")
            lines.append(f"📉 Último: ×{history[-1]}")
            await send_telegram(session, "\n".join(lines))
        await asyncio.sleep(3600)


async def monitor():
    async with aiohttp.ClientSession() as http:
        await send_telegram(http,
            "🟢 <b>Sultan Crash Monitor v3 INICIADO</b>\n"
            "📡 Conectado a Crashing Train\n"
            "🎯 Monitoreando: ×25, ×50, ×100\n\n"
            "💬 <b>Podés escribirme:</b>\n"
            "/estado — Ver probabilidades ahora\n"
            "/historial — Últimos resultados\n"
            "/resumen — Análisis completo\n"
            "/ayuda — Ver todos los comandos",
            priority=True)

        asyncio.create_task(status_update(http))
        asyncio.create_task(poll_commands(http))

        while True:
            try:
                log.info("Conectando WebSocket...")
                async with websockets.connect(
                    WS_URL,
                    extra_headers={
                        "Origin": "https://crash.hashesgames.com",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    ping_interval=20,
                    ping_timeout=10
                ) as ws:
                    log.info("✅ Conectado")
                    async for raw in ws:
                        try:
                            if isinstance(raw, str):
                                if raw == "2":
                                    await ws.send("3")
                                    continue
                                if raw.startswith("42"):
                                    data = json.loads(raw[2:])
                                    event = data[0]
                                    payload = data[1] if len(data) > 1 else {}
                                    if event == "gameStatus" and isinstance(payload, dict):
                                        status = payload.get("status", "")
                                        if status in ("crashed", "ended"):
                                            val = payload.get("crashedAt") or payload.get("multiplier")
                                            if val:
                                                crashed_at = round(float(val), 2)
                                                history.append(crashed_at)
                                                if len(history) > MAX_HISTORY:
                                                    history.pop(0)
                                                log.info(f"💥 ×{crashed_at} | {len(history)} rondas")
                                                await check_alerts(http, crashed_at)
                        except Exception as e:
                            log.error(f"Error msg: {e}")
            except Exception as e:
                log.error(f"Error WS: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(monitor())
