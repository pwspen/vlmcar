import React, { useState, useEffect, useCallback, useRef } from "react";

interface WebSocketData {
  image: string;
  dist?: number;
  notes?: string;
  action?: string;
}

const App = () => {
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [currentImage, setCurrentImage] = useState("");
  const [distance, setDistance] = useState<number | undefined>();
  const [notes, setNotes] = useState<string>("");
  const [action, setAction] = useState<string>("");
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
        const data: WebSocketData = JSON.parse(event.data);
        if (data.image) {
          setCurrentImage(data.image);
        }
        if (data.dist !== undefined) {
          setDistance(data.dist);
        }
        if (data.notes) {
          setNotes(data.notes);
        }
        if (data.action) {
          setAction(data.action);
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
    <div className="p-4 max-w-4xl mx-auto">
      <div className="mb-4 text-lg font-semibold">
        WebSocket Status: {connectionStatus}
      </div>

      {currentImage && (
        <div className="mb-6">
          <img
            src={currentImage}
            alt="Robot camera feed"
            className="w-full h-96 object-cover rounded-lg shadow-lg"
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 mt-4">
        <div className="p-4 bg-gray-50 rounded-lg">
          <div className="font-medium">Distance:</div>
          <div>{distance !== undefined ? `${distance} units` : "No data"}</div>
        </div>

        <div className="p-4 bg-gray-50 rounded-lg">
          <div className="font-medium">Notes:</div>
          <div>{notes || "No notes"}</div>
        </div>

        <div className="p-4 bg-gray-50 rounded-lg">
          <div className="font-medium">Action:</div>
          <div>{action || "No action"}</div>
        </div>
      </div>
    </div>
  );
};

export default App;
