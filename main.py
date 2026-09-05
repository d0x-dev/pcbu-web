import json
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import HTMLResponse
from typing import List

app = FastAPI()

# Configuration
SECRET_PIN = "2207"

# Connected bridge clients
bridge_connections: List[WebSocket] = []

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#000000">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Unlock</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500&display=swap');
        
        :root {
            --bg-color: #000000;
            --text-main: #ffffff;
            --text-muted: #737373;
            --key-bg: #171717;
            --key-active: #262626;
            --dot-empty: #262626;
            --dot-filled: #ffffff;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            -webkit-user-select: none;
            -webkit-tap-highlight-color: transparent;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        body {
            background-color: var(--bg-color);
            height: 100vh;
            height: 100dvh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: var(--text-main);
            overflow: hidden;
        }

        .container {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            max-width: 320px;
            padding: 20px;
        }

        .header {
            margin-bottom: 40px;
            text-align: center;
        }

        h1 {
            font-size: 16px;
            font-weight: 500;
            color: var(--text-main);
            margin-bottom: 8px;
        }

        .status-text {
            font-size: 13px;
            font-weight: 400;
            color: var(--text-muted);
            transition: color 0.3s ease;
        }

        .status-text.online {
            color: #10b981; /* Subtle emerald green */
        }

        .pin-display {
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-bottom: 60px;
            height: 12px;
        }

        .dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: var(--dot-empty);
            transition: background-color 0.15s ease, transform 0.15s ease;
        }

        .dot.active {
            background-color: var(--dot-filled);
            transform: scale(1.1);
        }

        .keypad {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px 24px;
            width: 100%;
        }

        .key {
            background: var(--key-bg);
            border-radius: 50%;
            width: 72px;
            height: 72px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            font-weight: 300;
            color: var(--text-main);
            cursor: pointer;
            margin: 0 auto;
            transition: background-color 0.1s ease, transform 0.1s ease;
        }

        @media (hover: hover) {
            .key:hover {
                background: var(--key-active);
            }
        }

        .key:active {
            background: var(--key-active);
            transform: scale(0.94);
        }

        .key.empty {
            background: transparent;
            cursor: default;
        }

        .key.action {
            font-size: 14px;
            font-weight: 400;
            background: transparent;
            color: var(--text-main);
        }

        .key.action:active {
            opacity: 0.5;
            transform: none;
            background: transparent;
        }

        #message {
            position: absolute;
            bottom: 40px;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            opacity: 0;
            transition: opacity 0.3s ease;
            text-align: center;
        }

        #message.visible {
            opacity: 1;
        }

        .shake { 
            animation: shake 0.4s cubic-bezier(.36,.07,.19,.97) both; 
        }

        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            20%, 60% { transform: translateX(-8px); }
            40%, 80% { transform: translateX(8px); }
        }
    </style>
</head>
<body>
    <div class="container" id="container">
        <div class="header">
            <h1>Enter Passcode</h1>
            <div class="status-text" id="ws-status">Connecting...</div>
        </div>

        <div class="pin-display" id="pin-display">
            <div class="dot" id="dot-1"></div>
            <div class="dot" id="dot-2"></div>
            <div class="dot" id="dot-3"></div>
            <div class="dot" id="dot-4"></div>
        </div>

        <div class="keypad">
            <div class="key" onclick="press('1')">1</div>
            <div class="key" onclick="press('2')">2</div>
            <div class="key" onclick="press('3')">3</div>
            <div class="key" onclick="press('4')">4</div>
            <div class="key" onclick="press('5')">5</div>
            <div class="key" onclick="press('6')">6</div>
            <div class="key" onclick="press('7')">7</div>
            <div class="key" onclick="press('8')">8</div>
            <div class="key" onclick="press('9')">9</div>
            <div class="key empty"></div>
            <div class="key" onclick="press('0')">0</div>
            <div class="key action" onclick="cancel()">Cancel</div>
        </div>
        <div style="text-align: center; margin-top: 15px;">
            <button onclick="lock()" style="background: transparent; border: 1px solid var(--text-muted); color: var(--text-main); border-radius: 8px; padding: 6px 12px; font-size: 13px; cursor: pointer; transition: all 0.2s ease;">Lock PC</button>
        </div>
    </div>
    <div id="message"></div>

    <script>
        let pin = "";
        let isProcessing = false;
        
        const vibrate = (pattern) => {
            if (navigator.vibrate) navigator.vibrate(pattern);
        };
        
        async function lock() {
            if (isProcessing) return;
            isProcessing = true;
            try {
                const response = await fetch('/lock', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                if (response.ok) {
                    vibrate(20);
                    showMessage("Lock Command Sent");
                }
            } catch (err) {
                showMessage("Network Error");
            }
            setTimeout(reset, 1000);
        }
        
        function press(digit) {
            if (isProcessing || pin.length >= 4) return;
            
            vibrate(10);
            pin += digit;
            updateDots();
            
            if (pin.length === 4) {
                submitPin();
            }
        }
        
        function cancel() {
            if (isProcessing || pin.length === 0) return;
            vibrate(10);
            pin = pin.slice(0, -1);
            updateDots();
        }
        
        function reset() {
            pin = "";
            updateDots();
            isProcessing = false;
        }
        
        function updateDots() {
            for (let i = 1; i <= 4; i++) {
                const dot = document.getElementById(`dot-${i}`);
                if (i <= pin.length) {
                    dot.classList.add('active');
                } else {
                    dot.classList.remove('active');
                }
            }
        }

        function showMessage(msg) {
            const msgEl = document.getElementById('message');
            msgEl.innerText = msg;
            msgEl.classList.add('visible');
            setTimeout(() => {
                msgEl.classList.remove('visible');
            }, 2000);
        }
        
        async function submitPin() {
            isProcessing = true;
            try {
                const response = await fetch('/unlock', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pin: pin })
                });
                
                const result = await response.json();
                
                if (response.ok && result.status === 'success') {
                    vibrate([20, 40, 20]);
                    showMessage("Unlocked");
                    setTimeout(reset, 1500);
                } else {
                    vibrate([40, 40, 40]);
                    const display = document.getElementById('pin-display');
                    display.classList.remove('shake');
                    void display.offsetWidth; // trigger reflow
                    display.classList.add('shake');
                    setTimeout(reset, 500);
                }
            } catch (err) {
                vibrate([40, 40, 40]);
                showMessage("Network Error");
                setTimeout(reset, 1000);
            }
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let statusWs;
        
        function connectStatusWs() {
            statusWs = new WebSocket(`${wsProtocol}//${window.location.host}/ws/status`);
            
            statusWs.onmessage = (event) => {
                const statusEl = document.getElementById('ws-status');
                if(event.data === "CONNECTED") {
                    statusEl.innerText = "Desktop Online";
                    statusEl.classList.add('online');
                } else {
                    statusEl.innerText = "Desktop Offline";
                    statusEl.classList.remove('online');
                }
            };
            
            statusWs.onclose = () => {
                const statusEl = document.getElementById('ws-status');
                statusEl.innerText = "Connecting...";
                statusEl.classList.remove('online');
                setTimeout(connectStatusWs, 3000);
            };
        }
        connectStatusWs();
    </script>
</body>
</html>
"""

@app.get("/")
async def get_index():
    return HTMLResponse(HTML_CONTENT)

@app.post("/unlock")
async def process_unlock(request: Request):
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid request")
        
    if data.get("pin") == SECRET_PIN:
        if not bridge_connections:
            return {"status": "error", "message": "PC OFFLINE"}
            
        for conn in bridge_connections:
            try:
                await conn.send_text("UNLOCK")
            except:
                pass
                
        return {"status": "success"}
    else:
        raise HTTPException(status_code=401, detail="Invalid PIN")

@app.post("/lock")
async def process_lock():
    if not bridge_connections:
        return {"status": "error", "message": "PC OFFLINE"}
        
    for conn in bridge_connections:
        try:
            await conn.send_text("LOCK")
        except:
            pass
            
    return {"status": "success"}

status_connections: List[WebSocket] = []

async def broadcast_status():
    status_msg = "CONNECTED" if bridge_connections else "DISCONNECTED"
    for conn in status_connections:
        try:
            await conn.send_text(status_msg)
        except:
            pass

@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    await websocket.accept()
    status_connections.append(websocket)
    try:
        await websocket.send_text("CONNECTED" if bridge_connections else "DISCONNECTED")
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        if websocket in status_connections:
            status_connections.remove(websocket)

@app.websocket("/ws/bridge")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    bridge_connections.append(websocket)
    await broadcast_status()
    try:
        while True:
            data = await websocket.receive_text()
    except Exception:
        pass
    finally:
        if websocket in bridge_connections:
            bridge_connections.remove(websocket)
        await broadcast_status()
