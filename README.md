# 🎰 Sultan Roulette Monitor

Bot que monitorea roulette.betandhold.com y te avisa por Telegram cuando las barras están en verde.

## ¿Qué hace?
- ✅ Detecta barras Lucky y Risky en verde
- ✅ Detecta letras del jackpot iluminadas  
- ✅ Te manda alerta a Telegram instantáneamente
- ✅ Corre 24/7 en la nube

---

## 🚀 DEPLOY EN RAILWAY (GRATIS)

### Paso 1 - Crear cuenta en Railway
1. Entrá a **railway.app**
2. Registrate con tu cuenta de GitHub (necesitás crear una en github.com si no tenés)

### Paso 2 - Subir los archivos a GitHub
1. Entrá a **github.com** y creá un repositorio nuevo llamado `sultan-monitor`
2. Subí estos 4 archivos:
   - `monitor.py`
   - `requirements.txt`
   - `Dockerfile`
   - `railway.json`

### Paso 3 - Deploy en Railway
1. En Railway, click en **"New Project"**
2. Elegí **"Deploy from GitHub repo"**
3. Seleccioná tu repo `sultan-monitor`
4. Railway detecta el Dockerfile automáticamente y empieza a correr

### Paso 4 - Listo
El bot empieza a monitorear y te manda un mensaje a Telegram confirmando que arrancó.

---

## ⚙️ Configuración (ya está configurada)
- **Token Telegram:** configurado
- **Chat ID:** configurado  
- **URL:** roulette.betandhold.com
- **Intervalo de chequeo:** cada 3 segundos

---

## 📱 Alertas que vas a recibir

**Barra en verde:**
```
🟢🔔 SULTAN ALERT - BARRA EN VERDE!
✅ Elementos verdes: Lucky, ...
💰 Pozo actual: 60 EVA
⚡ ¡Momento de jugar!
```

**Letras iluminadas:**
```
🔥 LETRAS ILUMINADAS!
📝 Letras activas: V E A
💰 Pozo: 60 EVA
⚡ ¡Jackpot acercándose!
```
