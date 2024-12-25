import React, { useState, useEffect, useCallback, useRef } from "react";

const App = () => {
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [currentImage, setCurrentImage] = useState("");
  const [ws, setWs] = useState<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const lastReconnectTime = useRef(0);

  const connectWebSocket = useCallback(() => {
    // Check if we've tried to reconnect recently (within last 500ms)
    const now = Date.now();
    if (now - lastReconnectTime.current < 500) {
      return () => {};
    }

    lastReconnectTime.current = now;
    reconnectAttempts.current += 1;

    // Only try to reconnect 3 times
    if (reconnectAttempts.current > 3) {
      setConnectionStatus("Failed to connect after 3 attempts");
      return () => {};
    }

    const websocket = new WebSocket("ws://192.168.137.70:3001/ws");

    websocket.onopen = () => {
      setConnectionStatus("Connected");
      reconnectAttempts.current = 0;
    };

    websocket.onclose = () => {
      setConnectionStatus(
        `Disconnected (Attempt ${reconnectAttempts.current}/3)`
      );
      // Try to reconnect after 500ms, but only if we haven't exceeded attempts
      if (reconnectAttempts.current < 3) {
        setTimeout(connectWebSocket, 500);
      }
    };

    websocket.onerror = (error) => {
      console.error("WebSocket error:", error);
      setConnectionStatus(
        `Error connecting (Attempt ${reconnectAttempts.current}/3)`
      );
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.image) {
          setCurrentImage(data.image);
        }
      } catch (error) {
        console.error("Error parsing message:", error);
      }
    };

    setWs(websocket);

    return () => {
      websocket.close();
    };
  }, []);

  useEffect(() => {
    const cleanup = connectWebSocket();

    return () => {
      if (ws) {
        ws.close();
      }
      cleanup();
    };
  }, [connectWebSocket, ws]);

  return (
    <div>
      <div>WebSocket Status: {connectionStatus}</div>
      {currentImage && <img src={currentImage} alt="Robot camera feed" />}
    </div>
  );
};

export default App;
