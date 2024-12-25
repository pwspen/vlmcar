import React, { useState, useEffect, useCallback, useRef } from "react";

interface WebSocketData {
  image?: string;
  [key: string]: any;
}

const App = () => {
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [currentImage, setCurrentImage] = useState("");
  const [data, setData] = useState<Record<string, any>>({});
  const [ws, setWs] = useState<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const lastReconnectTime = useRef(0);

  const connectWebSocket = useCallback(() => {
    const now = Date.now();
    if (now - lastReconnectTime.current < 500) {
      return () => {};
    }

    lastReconnectTime.current = now;
    reconnectAttempts.current += 1;

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
        const receivedData: WebSocketData = JSON.parse(event.data);
        const { image, ...otherData } = receivedData;

        if (image) {
          setCurrentImage(image);
        }

        setData(otherData);
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
        {Object.entries(data).map(([key, value]) => (
          <div key={key} className="p-4 bg-gray-50 rounded-lg">
            <div className="font-medium">{key}:</div>
            <div>{value?.toString() || "No data"}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default App;
