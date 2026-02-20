#!/usr/bin/env python3
"""
Sultan Roulette Monitor
Monitorea roulette.betandhold.com y avisa por Telegram cuando:
- La barra "Lucky" está en verde (oportunidad alta)
- La barra "Risky" está en verde (jackpot cerca)
- Letras del jackpot se iluminan
"""

import asyncio
import os
import logging
from playwright.async_api import async_playwright
import aiohttp

# ── CONFIGURACIÓN ──────────────────────────────────────────────
TELEGRAM_TOKEN = "8338023730:AAFSmB04tSjxkg8vn1wj1sPON0mquz-ORvQ"
CHAT_ID = "7706931467"
ROULETTE_URL = "https://roulette.betandhold.com/?ref=0x832e14f204d3cb19E67E1a614582357e0faE10ba"
CHECK_INTERVAL = 3  # segundos entre cada chequeo
# ───────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)


async def send_telegram(session: aiohttp.ClientSession, message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        async with session.post(url, json=payload) as r:
            if r.status == 200:
                log.info(f"✅ Telegram enviado: {message[:60]}")
            else:
                log.warning(f"Telegram error {r.status}: {await r.text()}")
    except Exception as e:
        log.error(f"Error enviando Telegram: {e}")


def parse_bar_value(style: str) -> float:
    """Extrae el porcentaje de una barra de progreso desde su style."""
    import re
    match = re.search(r'width:\s*([\d.]+)%', style or "")
    if match:
        return float(match.group(1))
    return 0.0


async def monitor():
    last_alerts = {}  # evita spam de alertas repetidas

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()

        log.info("Abriendo página...")
        await page.goto(ROULETTE_URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5)  # espera que cargue bien

        async with aiohttp.ClientSession() as http:
            await send_telegram(http, "🟢 Sultan Monitor INICIADO\nMonitoreando roulette.betandhold.com 24/7")
            log.info("Monitor activo")

            while True:
                try:
                    alerts = []

                    # ── Intentar leer datos desde el DOM / JavaScript ──
                    # Buscar barras de progreso por colores o atributos
                    
                    # Método 1: buscar elementos con texto Lucky/Risky y leer valores numéricos cercanos
                    page_text = await page.evaluate("() => document.body.innerText")
                    
                    # Buscar valores de Lucky y Risky en el texto
                    import re
                    
                    lucky_match = re.search(r'Lucky\s*\n?\s*(\d+)\s*/\s*(\d+)', page_text, re.IGNORECASE)
                    risky_match = re.search(r'Risky\s*\n?\s*(\d+)\s*/\s*(\d+)', page_text, re.IGNORECASE)
                    
                    # Método 2: leer estado visual buscando elementos coloreados
                    # Intentar obtener el color actual de las barras via JavaScript
                    bar_data = await page.evaluate("""() => {
                        const result = {};
                        
                        // Buscar todos los elementos y sus colores
                        const allElements = document.querySelectorAll('*');
                        
                        for (const el of allElements) {
                            const text = el.innerText || el.textContent || '';
                            const style = window.getComputedStyle(el);
                            
                            // Buscar barra Lucky
                            if (text.trim().toLowerCase().includes('lucky')) {
                                // Buscar el siguiente elemento que sea una barra
                                const parent = el.closest('[class*="bar"], [class*="progress"], [class*="meter"], [class*="fill"]') 
                                            || el.parentElement;
                                if (parent) {
                                    result.lucky_html = parent.outerHTML.substring(0, 500);
                                }
                            }
                            
                            // Buscar barra Risky  
                            if (text.trim().toLowerCase().includes('risky')) {
                                const parent = el.closest('[class*="bar"], [class*="progress"], [class*="meter"], [class*="fill"]')
                                            || el.parentElement;
                                if (parent) {
                                    result.risky_html = parent.outerHTML.substring(0, 500);
                                }
                            }
                        }
                        
                        // Buscar elementos verdes (RGB verde dominante)
                        const greenElements = [];
                        for (const el of allElements) {
                            const bg = style.backgroundColor;
                            const color = style.color;
                            if (bg && bg.includes('rgb')) {
                                const nums = bg.match(/\d+/g);
                                if (nums && nums.length >= 3) {
                                    const [r, g, b] = nums.map(Number);
                                    // Verde: G dominante, mayor que R y B
                                    if (g > 100 && g > r * 1.5 && g > b * 1.5) {
                                        const txt = el.innerText?.trim().substring(0, 30);
                                        if (txt) greenElements.push(txt);
                                    }
                                }
                            }
                        }
                        result.green_elements = [...new Set(greenElements)].slice(0, 10);
                        
                        // Buscar el pozo/jackpot amount
                        const amounts = [];
                        document.querySelectorAll('[class*="jackpot"], [class*="prize"], [class*="pool"], [class*="pot"]').forEach(el => {
                            const txt = el.innerText?.trim();
                            if (txt) amounts.push(txt);
                        });
                        result.jackpot_amounts = amounts.slice(0, 5);
                        
                        // Buscar letras iluminadas del jackpot
                        const litLetters = [];
                        document.querySelectorAll('[class*="letter"], [class*="char"]').forEach(el => {
                            const bg = window.getComputedStyle(el).backgroundColor;
                            const nums = bg?.match(/\d+/g);
                            if (nums && nums.length >= 3) {
                                const [r, g, b] = nums.map(Number);
                                if (g > 100 && g > r * 1.3) {
                                    litLetters.push(el.innerText?.trim());
                                }
                            }
                        });
                        result.lit_letters = litLetters;
                        
                        return result;
                    }""")

                    # Procesar resultados
                    green_els = bar_data.get('green_elements', [])
                    jackpot_amounts = bar_data.get('jackpot_amounts', [])
                    lit_letters = bar_data.get('lit_letters', [])

                    # Analizar texto de la página para valores numéricos
                    lucky_val = 0
                    risky_val = 0
                    
                    if lucky_match:
                        lucky_val = int(lucky_match.group(1))
                        lucky_max = int(lucky_match.group(2))
                        lucky_pct = (lucky_val / lucky_max) * 100 if lucky_max > 0 else 0
                    
                    if risky_match:
                        risky_val = int(risky_match.group(1))
                        risky_max = int(risky_match.group(2))
                        risky_pct = (risky_val / risky_max) * 100 if risky_max > 0 else 0

                    log.info(f"Verde detectado: {green_els} | Jackpot: {jackpot_amounts}")

                    # ── Generar alertas ──
                    
                    # Alerta si hay elementos verdes (barras en verde)
                    if green_els:
                        alert_key = f"green_{','.join(green_els[:3])}"
                        if last_alerts.get(alert_key) != True:
                            jackpot_txt = ', '.join(jackpot_amounts) if jackpot_amounts else 'N/A'
                            msg = (
                                "🟢🔔 <b>SULTAN ALERT - BARRA EN VERDE!</b>\n\n"
                                f"✅ Elementos verdes: {', '.join(green_els[:5])}\n"
                                f"💰 Pozo actual: {jackpot_txt}\n"
                                f"⚡ ¡Momento de jugar!\n\n"
                                f"🎰 roulette.betandhold.com"
                            )
                            alerts.append(msg)
                            last_alerts[alert_key] = True
                    else:
                        # Reset alertas cuando no hay verde
                        for key in list(last_alerts.keys()):
                            if key.startswith("green_"):
                                last_alerts.pop(key, None)

                    # Alerta por letras iluminadas
                    if lit_letters:
                        letters_key = f"letters_{''.join(lit_letters)}"
                        if last_alerts.get(letters_key) != True:
                            msg = (
                                "🔥 <b>LETRAS ILUMINADAS!</b>\n\n"
                                f"📝 Letras activas: {' '.join(lit_letters)}\n"
                                f"💰 Pozo: {', '.join(jackpot_amounts) if jackpot_amounts else 'N/A'}\n"
                                "⚡ ¡Jackpot acercándose!"
                            )
                            alerts.append(msg)
                            last_alerts[letters_key] = True

                    # Enviar alertas
                    for alert in alerts:
                        await send_telegram(http, alert)

                except Exception as e:
                    log.error(f"Error en ciclo: {e}")
                    # Si la página se cayó, intentar recargar
                    try:
                        await page.reload(wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(5)
                    except:
                        pass

                await asyncio.sleep(CHECK_INTERVAL)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(monitor())
