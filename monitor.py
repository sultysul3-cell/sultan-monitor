#!/usr/bin/env python3
"""Sultan Crash Monitor v4 - Conexion estable con socketio"""

import asyncio
import json
import logging
import aiohttp

TELEGRAM_TOKEN = "8338023730:AAFSmB04tSjxkg8vn1wj1sPON0mquz-ORvQ"
CHAT_ID = "7706931467"
BASE_URL = "https://crashdata.hashesgames.com"

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
sid = None


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
                msg = (f"🚨🔥 <b>URGENTE - {key.upper()}!</b>\n\n"
                       f"📊 Probabilidad: <b>{prob}%</b>\n"
                       f"🎯 Objetivo: ×{mult}\n"
                       f"🔢 Rondas sin salir: <b>{misses}</b>\n"
                       f"📉 Último crash: ×{crashed_at}\n\n"
                       f"⚡ <b>¡MÁXIMA OPORTUNIDAD!</b>")
                await send_telegram(session, msg, priority=True)
                last_alerts[alert_key] = True
                last_alerts.pop(f"{key}_alert_{misses // 5}", None)
        elif prob >= t["alert"]:
            alert_key = f"{key}_alert_{misses // 5}"
            if alert_key not in last_alerts:
                msg = (f"⚠️ <b>ALERTA - {key.upper()}</b>\n\n"
                       f"📊 Probabilidad: <b>{prob}%</b>\n"
                       f"🎯 Objetivo: ×{mult}\n"
                       f"🔢 Rondas sin salir: <b>{misses}</b>\n"
                       f"📉 Último crash: ×{crashed_at}\n\n"
                       f"👀 Probabilidad muy alta")
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
        emoji = "🔴" if prob >= 99.6 else "🟡" if prob >= 99.0 else "🟠" if prob >= 90 else "🟢"
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
    for val in reversed(ultimos):
        emoji = "🔥" if val >= 100 else "💥" if val >= 50 else "⭐" if val >= 25 else "✅" if val >= 10 else "💀"
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
        pct_esp = round(1 / mult * 100, 1)
        prob, misses = calc_prob(mult, history)
        estado = "⚠️ Sale MENOS de lo esperado" if pct_real < pct_esp * 0.7 else "📈 Sale MÁS de lo esperado" if pct_real > pct_esp * 1.3 else "✅ Normal"
        lines.append(f"🎯 <b>×{mult}</b>\n   Real: {pct_real}% | Esperado: {pct_esp}%\n   {estado}\n   Prob. acumulada: {prob}%\n")
    lines.append(f"🏆 Máximo: ×{max(history)}")
    lines.append(f"💀 Mínimo: ×{min(history)}")
    await send_telegram(session, "\n".join(lines))


async def check_commands(session):
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 1}
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    text = update.get("message", {}).get("text", "").lower().strip()
                    if text == "/estado":
                        await cmd_estado(session)
                    elif text == "/historial":
                        await cmd_historial(session)
                    elif text == "/resumen":
                        await cmd_resumen(session)
                    elif text in ("/ayuda", "/help"):
                        await send_telegram(session,
                            "🤖 <b>Comandos:</b>\n\n"
                            "/estado — Probabilidades actuales\n"
                            "/historial — Últimos 15 resultados\n"
                            "/resumen — Análisis completo\n"
                            "/ayuda — Esta ayuda")
    except:
        pass


async def poll_commands(session):
    while True:
        await check_commands(session)
        await asyncio.sleep(3)


async def get_sid(session):
    """Obtener session ID de socket.io via polling"""
    url = f"{BASE_URL}/socket.io/?EIO=4&transport=polling"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            text = await r.text()
            # Respuesta: 0{"sid":"...","upgrades":["websocket"],...}
            if text.startswith("0"):
                data = json.loads(text[1:])
                return data.get("sid")
    except Exception as e:
        log.error(f"Error get_sid: {e}")
    return None


async def poll_game_data(session):
    """Polling de datos del juego via HTTP en lugar de WebSocket"""
    global history
    
    while True:
        try:
            # Intentar obtener datos via polling de socket.io
            sid = await get_sid(session)
            if not sid:
                log.error("No se pudo obtener SID")
                await asyncio.sleep(5)
                continue
            
            log.info(f"SID obtenido: {sid[:10]}...")
            
            # Enviar mensaje de conexion
            poll_url = f"{BASE_URL}/socket.io/?EIO=4&transport=polling&sid={sid}"
            
            # Enviar "2probe" para upgrade
            async with session.post(poll_url, data="2probe", timeout=aiohttp.ClientTimeout(total=10)) as r:
                pass
            
            # Loop de polling
            consecutive_errors = 0
            while consecutive_errors < 10:
                try:
                    async with session.get(poll_url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                        if r.status == 200:
                            text = await r.text()
                            consecutive_errors = 0
                            
                            # Parsear mensajes
                            # Formato: LENGTH:MESSAGE
                            i = 0
                            while i < len(text):
                                # Buscar el separador de longitud
                                colon = text.find(':', i)
                                if colon == -1:
                                    break
                                try:
                                    length = int(text[i:colon])
                                    msg = text[colon+1:colon+1+length]
                                    i = colon + 1 + length
                                    
                                    # Procesar mensaje socket.io
                                    if msg.startswith("42"):
                                        data = json.loads(msg[2:])
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
                                                    await check_alerts(session, crashed_at)
                                except (ValueError, json.JSONDecodeError):
                                    break
                        else:
                            consecutive_errors += 1
                            await asyncio.sleep(2)
                except Exception as e:
                    log.error(f"Error polling: {e}")
                    consecutive_errors += 1
                    await asyncio.sleep(2)
                
                # Enviar heartbeat
                try:
                    async with session.post(poll_url, data="2", timeout=aiohttp.ClientTimeout(total=5)) as r:
                        pass
                except:
                    pass
                    
        except Exception as e:
            log.error(f"Error general: {e}")
            await asyncio.sleep(5)


async def ws_game_data(session):
    """Conexion WebSocket mejorada con reconexion inteligente"""
    import websockets
    
    WS_URL = "wss://crashdata.hashesgames.com/socket.io/?EIO=4&transport=websocket"
    
    while True:
        try:
            log.info("Conectando WS...")
            async with websockets.connect(
                WS_URL,
                extra_headers={
                    "Origin": "https://crash.hashesgames.com",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "es-ES,es;q=0.9",
                },
                ping_interval=None,  # Manejar ping manualmente
                close_timeout=5,
                max_size=10_000_000,
            ) as ws:
                log.info("✅ WS Conectado")
                last_ping = asyncio.get_event_loop().time()
                
                async for raw in ws:
                    now = asyncio.get_event_loop().time()
                    
                    if isinstance(raw, str):
                        # Socket.IO ping
                        if raw == "2":
                            await ws.send("3")
                            last_ping = now
                            continue
                        
                        # Socket.IO handshake
                        if raw.startswith("0"):
                            try:
                                data = json.loads(raw[1:])
                                log.info(f"Handshake OK, pingInterval={data.get('pingInterval')}")
                            except:
                                pass
                            continue
                        
                        # Socket.IO event
                        if raw.startswith("42"):
                            try:
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
                                            await check_alerts(session, crashed_at)
                                    
                                    elif status == "running":
                                        log.debug(f"🚀 ×{payload.get('multiplier', '?')}")
                                        
                            except json.JSONDecodeError:
                                pass
                    
                    # Ping manual cada 20s si no hay actividad
                    if now - last_ping > 20:
                        await ws.send("2")
                        last_ping = now
                        
        except Exception as e:
            log.error(f"Error WS: {e}")
            await asyncio.sleep(3)


async def status_update(session):
    await asyncio.sleep(3600)
    while True:
        if history:
            lines = ["📊 <b>Resumen horario</b>\n"]
            for t in TARGETS:
                prob, misses = calc_prob(t["mult"], history)
                emoji = "🔴" if prob >= 99.6 else "🟡" if prob >= 99.0 else "🟠" if prob >= 90 else "🟢"
                lines.append(f"{emoji} ×{t['mult']}: {prob}% ({misses} rondas)")
            lines.append(f"\n📈 Total: {len(history)} rondas")
            lines.append(f"📉 Último: ×{history[-1]}")
            await send_telegram(session, "\n".join(lines))
        await asyncio.sleep(3600)


async def monitor():
    async with aiohttp.ClientSession() as http:
        await send_telegram(http,
            "🟢 <b>Sultan Crash Monitor v4 INICIADO</b>\n"
            "📡 Conectando a Crashing Train...\n"
            "🎯 Monitoreando: ×25, ×50, ×100\n\n"
            "💬 Comandos: /estado /historial /resumen /ayuda",
            priority=True)

        asyncio.create_task(status_update(http))
        asyncio.create_task(poll_commands(http))
        
        # Usar WebSocket mejorado
        await ws_game_data(http)


if __name__ == "__main__":
    asyncio.run(monitor())
