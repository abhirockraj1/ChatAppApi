# main.py
import asyncio
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from typing import List, Dict, Optional
from pydantic import BaseModel

app = FastAPI(title="FastAPI Localized Chat App")

# Placeholder API URL for language translation
TRANSLATION_API_URL = "http://localhost:8001/translate"  # Replace with your actual translation API URL

# In-memory storage for client preferences (replace with a database in a real app)
client_preferences: Dict[str, str] = {}  # {client_id: language_code}

# Simple HTML page for testing (with language selection)
html = """
<!DOCTYPE html>
<html>
  <head>
    <title>Localized Chat</title>
  </head>
  <body>
    <h1>WebSocket Chat (Localized)</h1>
    <p>Your ID: <span id="ws-id"></span></p>
    <label for="language">Select Language:</label>
    <select id="language" onchange="setLanguagePreference()">
      <option value="en">English</option>
      <option value="fr">French</option>
      <option value="es">Hindi</option>
          </select>
    <form action="" onsubmit="sendMessage(event)">
      <input type="text" id="messageText" autocomplete="off"/>
      <button>Send</button>
    </form>
    <ul id='messages'>
    </ul>
    <script>
      var clientId = Date.now() + Math.random().toString(16).substring(2); // Simple unique-ish ID
      document.querySelector("#ws-id").textContent = clientId;
      var preferredLanguage = localStorage.getItem('preferredLanguage') || 'en'; // Default to English
      document.getElementById('language').value = preferredLanguage;

      function setLanguagePreference() {
        var selectedLanguage = document.getElementById('language').value;
        localStorage.setItem('preferredLanguage', selectedLanguage);
        console.log("Setting preferred language to:", selectedLanguage);
        // Optionally, inform the server about the language preference upon change
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "set_language", language: selectedLanguage }));
        }
      }

      // Construct WebSocket URL dynamically based on the current page location
      var ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
      var ws_url = `<span class="math-inline">\{ws\_scheme\}\://</span>{window.location.host}/ws/${clientId}`;
      console.log("Connecting to WebSocket:", ws_url); // For debugging
      var ws = new WebSocket(ws_url);

      ws.onopen = function(event) {
        console.log("WebSocket connection opened");
        // Send initial language preference to the server
        ws.send(JSON.stringify({ type: "set_language", language: preferredLanguage }));
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
          ws.send(JSON.stringify({ type: "message", text: input.value }));
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

class ConnectionManager:
  def __init__(self):
    self.active_connections: Dict[str, WebSocket] = {}

  async def connect(self, websocket: WebSocket, client_id: str):
    await websocket.accept()
    self.active_connections[client_id] = websocket
    print(f"Client {client_id} connected. Total clients: {len(self.active_connections)}")

  def disconnect(self, client_id: str):
    if client_id in self.active_connections:
      del self.active_connections[client_id]
      print(f"Client {client_id} disconnected. Total clients: {len(self.active_connections)}")

  async def send_personal_message(self, message: str, client_id: str):
    if client_id in self.active_connections:
      websocket = self.active_connections[client_id]
      try:
        await websocket.send_text(message)
      except Exception as e:
        print(f"Error sending personal message to {client_id}: {e}")

  async def broadcast(self, message: str, sender_id: str = "System", target_language: Optional[str] = None):
    disconnected_clients = []
    connections = list(self.active_connections.items()) # Iterate over a copy
    for client_id, websocket in connections:
      try:
        if target_language and client_id in client_preferences and client_preferences[client_id] == target_language:
          await websocket.send_text(message)
        elif not target_language: # Broadcast to all if no target language specified
          await websocket.send_text(message)
      except Exception as e:
        print(f"Error broadcasting to {client_id}: {e}. Marking for disconnection.")
        disconnected_clients.append(client_id)

    for client_id in disconnected_clients:
      if client_id in self.active_connections: # Check if not already disconnected
        self.disconnect(client_id)

manager = ConnectionManager()
http_client = httpx.AsyncClient()

class TranslationRequest(BaseModel):
  text: str
  target_language: str

async def fetch_translation(text: str, target_language: str) -> Optional[str]:
  """Placeholder for calling a translation API."""
  try:
    response = await http_client.post(
      TRANSLATION_API_URL,
      json={"text": text, "target_language": target_language}
    )
    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    return response.json().get("translated_text")
  except httpx.HTTPError as e:
    print(f"Error calling translation API: {e}")
    return None
  except Exception as e:
    print(f"Unexpected error during translation: {e}")
    return None

@app.get("/")
async def get():
  """Serves the simple HTML page for testing."""
  return HTMLResponse(html)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
  """Handles WebSocket connections for the chat with language preferences."""
  await manager.connect(websocket, client_id)

  try:
    while True:
        data = await websocket.receive_json()
        if "type" in data:
            if data["type"] == "set_language" and "language" in data:
                language_code = data["language"]
                client_preferences[client_id] = language_code
                print(f"Client {client_id} set language preference to: {language_code}")
            elif data["type"] == "message" and "text" in data:
                message_text = data["text"]
                await manager.broadcast(f"Client #{client_id}: {message_text}", sender_id=client_id)     
  except WebSocketDisconnect:
    manager.disconnect(client_id)
    await manager.broadcast(f"System: Client #{client_id} left the chat", sender_id=client_id)
  except Exception as e:
    print(f"Unexpected error with client {client_id}: {e}")
    # Ensure disconnection on unexpected errors
    if client_id in manager.active_connections:
        manager.disconnect(client_id)
        await manager.broadcast(f"System: Client #{client_id} disconnected due to an error.", sender_id=client_id)          
