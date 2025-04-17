# main.py
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Dict

app = FastAPI(title="FastAPI Chat App")

# Simple HTML page for testing (with corrected WebSocket JS)
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat (Compose)</h1>
        <p>Your ID: <span id="ws-id"></span></p>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var clientId = Date.now() + Math.random().toString(16).substring(2); // Simple unique-ish ID
            document.querySelector("#ws-id").textContent = clientId;

            // Construct WebSocket URL dynamically based on the current page location
            var ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
            var ws_url = `${ws_scheme}://${window.location.host}/ws/${clientId}`;
            console.log("Connecting to WebSocket:", ws_url); // For debugging
            var ws = new WebSocket(ws_url);

            ws.onopen = function(event) {
                console.log("WebSocket connection opened");
                // Optional: Send a message upon connection if needed
                // ws.send(JSON.stringify({type: "join", client_id: clientId}));
            };

            ws.onmessage = function(event) {
                var messages = document.getElementById('messages');
                var message = document.createElement('li');
                var content = document.createTextNode(event.data);
                message.appendChild(content);
                messages.appendChild(message);
            };

            function sendMessage(event) {
                var input = document.getElementById("messageText");
                if (input.value && ws.readyState === WebSocket.OPEN) { // Check if input has value & connection is open
                    ws.send(input.value);
                    input.value = '';
                } else if (ws.readyState !== WebSocket.OPEN) {
                    console.error("WebSocket is not open. ReadyState: " + ws.readyState);
                    alert("WebSocket connection is not open. Cannot send message.");
                }
                event.preventDefault();
            }

            ws.onclose = function(event) {
                console.log("WebSocket connection closed", event);
                var item = document.createElement('li');
                item.style.color = 'orange';
                item.textContent = 'Connection closed. Please refresh.';
                document.getElementById('messages').appendChild(item);
            };

            ws.onerror = function(error) {
                console.error("WebSocket Error: ", error);
                var item = document.createElement('li');
                item.style.color = 'red';
                item.textContent = 'WebSocket error occurred. Check console.';
                document.getElementById('messages').appendChild(item);
            };
        </script>
    </body>
</html>
"""

# In-memory storage for active connections (same limitations apply)
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Client {client_id} connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            # Optional: Ensure websocket is closed before deleting reference
            # websocket = self.active_connections[client_id]
            # try:
            #    await websocket.close()
            # except RuntimeError: # Handle cases where it might already be closed
            #    pass
            del self.active_connections[client_id]
            print(f"Client {client_id} disconnected. Total clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"Error sending personal message to {client_id}: {e}")

    async def broadcast(self, message: str, sender_id: str = "System"):
        disconnected_clients = []
        connections = list(self.active_connections.items()) # Iterate over a copy
        for client_id, websocket in connections:
            # if client_id == sender_id: # Optionally skip sender
            #     continue
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to {client_id}: {e}. Marking for disconnection.")
                disconnected_clients.append(client_id)

        for client_id in disconnected_clients:
             if client_id in self.active_connections: # Check if not already disconnected by another process
                self.disconnect(client_id)

manager = ConnectionManager()

@app.get("/")
async def get():
    """Serves the simple HTML page for testing."""
    return HTMLResponse(html)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Handles WebSocket connections for the chat."""
    await manager.connect(websocket, client_id)
    await manager.broadcast(f"System: Client #{client_id} joined the chat", sender_id=client_id)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Client #{client_id}: {data}", sender_id=client_id)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(f"System: Client #{client_id} left the chat", sender_id=client_id)
    except Exception as e:
        print(f"Unexpected error with client {client_id}: {e}")
        # Ensure disconnection on unexpected errors
        if client_id in manager.active_connections:
            manager.disconnect(client_id)
            await manager.broadcast(f"System: Client #{client_id} disconnected due to an error.", sender_id=client_id)
