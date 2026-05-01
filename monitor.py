#!/usr/bin/env python3
"""
Sultan Crash Monitor - Crashing Train (Hashes Games)
Alertas de probabilidad acumulada para x25, x50, x100
"""

import asyncio
import json
import logging
import aiohttp
import websockets

TELEGRAM_TOKEN = "8338023730:AAFSmB04tSjxkg8vn1wj1sPON0mquz-ORvQ"
CHAT_ID = "7706931467"
WS_URL = "wss://crashdata.hashesgames.com/socket.io/?EIO=4&transport=websocket"

# Umbrales ajustados
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


def calc_prob(multiplier: float, results: list) -> tuple:
    """
    Retorna (probabilidad_acumulada, rondas_sin_salir)
    """
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
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_notification": not priority
    }
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                log.info(f"✅ Enviado: {msg[:60]}")
    except Exception as e:
        log.error(f"Error Telegram: {e}")


async def check_alerts(session, crashed_at: float):
    for t in TARGETS:
        mult = t["mult"]
        key = t["key"]
        prob, misses = calc_prob(mult, history)

        # Alerta URGENTE 99.6%
        if prob >= t["urgent"]:
            alert_key = f"{key}_urgent_{misses // 5}"
            if alert_key not in last_alerts:
                msg = (
                    f"🚨🔥 <b>URGENTE - {key.upper()}!</b>\n\n"
                    f"📊 Probabilidad: <b>{prob}%</b>\n"
                    f"🎯 Objetivo: ×{mult}\n"
                    f"🔢 Rondas sin salir: <b>{misses}</b>\n"
                    f"📉 Último crash: ×{crashed_at}\n\n"
                    f"⚡ <b>¡MÁXIMA OPORTUNIDAD - JUGÁ AHORA!</b>"
                )
                await send_telegram(session, msg, priority=True)
                last_alerts[alert_key] = True
                last_alerts.pop(f"{key}_alert_{misses // 5}", None)

        # Alerta NORMAL 99%
        elif prob >= t["alert"]:
            alert_key = f"{key}_alert_{misses // 5}"
            if alert_key not in last_alerts:
                msg = (
                    f"⚠️ <b>ALERTA - {key.upper()}</b>\n\n"
                    f"📊 Probabilidad: <b>{prob}%</b>\n"
                    f"🎯 Objetivo: ×{mult}\n"
                    f"🔢 Rondas sin salir: <b>{misses}</b>\n"
                    f"📉 Último crash: ×{crashed_at}\n\n"
                    f"👀 Probabilidad muy alta, prestá atención"
                )
                await send_telegram(session, msg, priority=True)
                last_alerts[alert_key] = True

        else:
            # Limpiar alertas cuando el multiplicador salió
            for k in list(last_alerts.keys()):
                if k.startswith(key):
                    last_alerts.pop(k)


async def status_update(session):
    """Resumen cada hora"""
    await asyncio.sleep(300)  # primera en 5 min
    while True:
        if history:
            lines = ["📊 <b>Sultan Monitor - Estado actual</b>\n"]
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
                lines.append(f"{emoji} ×{t['mult']}: {prob}% ({misses} rondas sin salir)")
            lines.append(f"\n📈 Rondas analizadas: {len(history)}")
            lines.append(f"📉 Último crash: ×{history[-1]}")
            await send_telegram(session, "\n".join(lines))
        await asyncio.sleep(3600)  # cada hora


async def monitor():
    async with aiohttp.ClientSession() as http:
        await send_telegram(http,
            "🟢 <b>Sultan Crash Monitor INICIADO</b>\n"
            "📡 Conectado a Crashing Train - Hashes Games\n"
            "🎯 Monitoreando: ×25, ×50, ×100\n"
            "⚠️ Alerta a 99% de prob. acumulada\n"
            "🚨 Urgente a 99.6% de prob. acumulada",
            priority=True)

        asyncio.create_task(status_update(http))

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
                    log.info("✅ WebSocket conectado")

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

                                        elif status == "running":
                                            log.debug(f"🚀 ×{payload.get('multiplier', '?')}")

                        except Exception as e:
                            log.error(f"Error msg: {e}")

            except Exception as e:
                log.error(f"Error WS: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(monitor())
