import React, { useState, useEffect, useCallback, useRef } from "react";

interface WebSocketData {
  image?: string;
  timestamp?: number;
  [key: string]: any;
}

interface DataSnapshot {
  id: number;
  image?: string;
  data: Record<string, any>;
  timestamp: number;
}

const App = () => {
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [dataHistory, setDataHistory] = useState<DataSnapshot[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const lastReconnectTime = useRef(0);
  const reconnectAttempts = useRef(0);
  const nextId = useRef(0);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the right when new data arrives
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollLeft =
        scrollContainerRef.current.scrollWidth;
    }
  }, [dataHistory]);

  const connectWebSocket = useCallback(() => {
    const now = Date.now();
    if (now - lastReconnectTime.current < 500) {
      return () => {};
    }
    lastReconnectTime.current = now;
    reconnectAttempts.current += 1;
    const reconnectAttemptPeriod = 1000;

    const websocket = new WebSocket("ws://192.168.137.70:3001/ws");

    websocket.onopen = () => {
      setConnectionStatus("Connected");
      reconnectAttempts.current = 0;
    };

    websocket.onclose = () => {
      setConnectionStatus(
        `Disconnected (Retrying in ${Math.round(
          reconnectAttemptPeriod / 1000
        )}s)`
      );
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      reconnectTimeoutRef.current = setTimeout(
        connectWebSocket,
        reconnectAttemptPeriod
      );
    };

    websocket.onerror = (error) => {
      console.error("WebSocket error:", error);
      setConnectionStatus("Connection error - will retry automatically");
    };

    websocket.onmessage = (event) => {
      try {
        const receivedData: WebSocketData = JSON.parse(event.data);
        const { image, ...otherData } = receivedData;

        const newSnapshot: DataSnapshot = {
          id: nextId.current++,
          image,
          data: otherData,
          timestamp: Date.now(),
        };

        setDataHistory((prev) => [...prev, newSnapshot].slice(-10)); // Keep last 10 snapshots
      } catch (error) {
        console.error("Error parsing message:", error);
      }
    };

    setWs(websocket);
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      websocket.close();
    };
  }, []);

  useEffect(() => {
    const cleanup = connectWebSocket();
    return () => {
      if (ws) {
        ws.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      cleanup();
    };
  }, [connectWebSocket, ws]);

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <div className="p-4">
      <div className="mb-4 text-lg font-semibold">
        WebSocket Status: {connectionStatus}
      </div>

      <div className="fixed inset-x-0 bottom-0 h-3/4 bg-gray-50">
        <div className="h-full">
          <div
            ref={scrollContainerRef}
            className="h-full overflow-x-auto whitespace-nowrap"
            style={{ scrollBehavior: "smooth" }}
          >
            <div className="inline-flex gap-4 p-4">
              {dataHistory.map((snapshot) => (
                <div
                  key={snapshot.id}
                  className="inline-block w-96 bg-white rounded-xl shadow-lg overflow-hidden"
                >
                  <div className="p-3 bg-gray-50 border-b text-sm text-gray-600">
                    {formatTimestamp(snapshot.timestamp)}
                  </div>

                  {snapshot.image && (
                    <div className="p-4">
                      <img
                        src={snapshot.image}
                        alt={`Snapshot ${snapshot.id}`}
                        className="w-full h-48 object-cover rounded-lg"
                      />
                    </div>
                  )}

                  <div className="p-4 space-y-3 max-h-96 overflow-y-auto">
                    {Object.entries(snapshot.data).map(([key, value]) => (
                      <div key={key} className="bg-gray-50 p-3 rounded-lg">
                        <div className="font-medium text-gray-700">{key}</div>
                        <div className="text-gray-600 break-words">
                          {value?.toString() || "No data"}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
