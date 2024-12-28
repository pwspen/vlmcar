import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  DataSnapshot,
  LogFile,
  WebSocketData,
  LogSnapshotProps,
  LogViewerProps,
} from "./types";
import { loadLogFile } from "./LogLoader";

const LogSnapshot: React.FC<LogSnapshotProps> = ({
  snapshot,
  formatTimestamp = (timestamp: number) =>
    new Date(timestamp).toLocaleTimeString(),
}) => {
  return (
    <div className="inline-block w-96 bg-white rounded-xl shadow-lg overflow-hidden">
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
          <div
            key={key}
            className="bg-gray-50 p-3 rounded-lg break-words whitespace-normal"
          >
            <div className="font-medium text-gray-700">{key}</div>
            <div className="text-gray-600 break-words">
              {value?.toString() || "No data"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const LogViewer: React.FC<LogViewerProps> = ({
  snapshots = [],
  mode = "live",
  playbackDelay = 1000,
  logs_fpath,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loadedSnapshots, setLoadedSnapshots] = useState<DataSnapshot[]>([]);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const activeSnapshots = logs_fpath ? loadedSnapshots : snapshots;
  const visibleSnapshots =
    mode === "live"
      ? activeSnapshots
      : activeSnapshots.slice(0, currentIndex + 1);

  useEffect(() => {
    if (mode === "live" && logs_fpath) {
      throw new Error("Cannot provide logs_fpath in live mode");
    }

    const loadData = async () => {
      if (mode === "playback" && logs_fpath) {
        const loaded = await loadLogFile(logs_fpath);
        setLoadedSnapshots(loaded);
        setCurrentIndex(0);
        setIsPlaying(false);
      }
    };

    loadData();
  }, [mode, logs_fpath]);

  // For live mode: scroll to the right when new data arrives
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollLeft =
        scrollContainerRef.current.scrollWidth;
    }
  }, [visibleSnapshots.length]);

  // Playback logic
  useEffect(() => {
    if (mode === "playback" && isPlaying) {
      const activeSnapshots = logs_fpath ? loadedSnapshots : snapshots;
      const intervalId = setInterval(() => {
        setCurrentIndex((prevIndex) => {
          if (prevIndex >= activeSnapshots.length - 1) {
            setIsPlaying(false);
            return prevIndex;
          }
          return prevIndex + 1;
        });
      }, playbackDelay);

      return () => clearInterval(intervalId);
    }
  }, [
    isPlaying,
    playbackDelay,
    mode,
    snapshots.length,
    loadedSnapshots.length,
    logs_fpath,
  ]);

  const togglePlayback = () => {
    const activeSnapshots = logs_fpath ? loadedSnapshots : snapshots;
    if (!isPlaying && currentIndex >= activeSnapshots.length - 1) {
      setCurrentIndex(0); // Reset to start when reaching the end
    }
    setIsPlaying(!isPlaying);
  };

  return (
    <div className="h-full">
      {mode === "playback" && (
        <div className="flex items-center justify-center mb-4">
          <button
            onClick={togglePlayback}
            className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
          >
            {isPlaying ? "Pause" : "Play"}
          </button>
          <div className="ml-4 text-gray-600">
            Showing {currentIndex + 1} of {activeSnapshots.length} snapshots
          </div>
        </div>
      )}
      <div
        ref={scrollContainerRef}
        className="h-full overflow-x-auto whitespace-nowrap"
        style={{ scrollBehavior: "smooth" }}
      >
        <div className="inline-flex gap-4 p-4">
          {visibleSnapshots.map((snapshot) => (
            <LogSnapshot key={snapshot.id} snapshot={snapshot} />
          ))}
        </div>
      </div>
    </div>
  );
};

const App = () => {
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [dataHistory, setDataHistory] = useState<DataSnapshot[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const lastReconnectTime = useRef(0);
  const reconnectAttempts = useRef(0);
  const nextId = useRef(0);
  const currentLogFile = useRef<LogFile | null>(null);
  const logFileName = useRef<string>("");

  const getLogFileName = () => {
    const now = new Date();
    const day = String(now.getDate()).padStart(2, "0");
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const year = now.getFullYear();
    const hour = String(now.getHours()).padStart(2, "0");
    const minute = String(now.getMinutes()).padStart(2, "0");
    const second = String(now.getSeconds()).padStart(2, "0");

    return `run_${day}_${month}_${year}_${hour}${minute}${second}.json`;
  };

  const downloadLog = () => {
    if (!currentLogFile.current) return;

    try {
      const jsonString = JSON.stringify(currentLogFile.current, null, 2);
      const blob = new Blob([jsonString], { type: "application/json" });
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = logFileName.current;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      console.log(`Log downloaded as ${logFileName.current}`);
    } catch (error) {
      console.error("Error downloading log file:", error);
    }
  };

  const connectWebSocket = useCallback(() => {
    const now = Date.now();
    if (now - lastReconnectTime.current < 500) {
      return () => {};
    }
    lastReconnectTime.current = now;
    reconnectAttempts.current += 1;
    const reconnectAttemptPeriod = 1000;

    // Initialize new log file
    logFileName.current = getLogFileName();
    currentLogFile.current = {
      startTime: now,
      snapshots: [],
    };

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
      // Download log file when connection closes
      if (currentLogFile.current?.snapshots.length) {
        downloadLog();
      }

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

        // Update current log file
        if (currentLogFile.current) {
          currentLogFile.current.snapshots.push(newSnapshot);
        }

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

  return (
    <div className="p-4">
      <div className="fixed inset-x-0 bottom-0 h-full bg-gray-50">
        <div className="flex items-center justify-between mb-4 px-4">
          <div className="text-lg font-semibold">
            WebSocket Status: {connectionStatus}
          </div>
          <button
            onClick={downloadLog}
            className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
            disabled={!currentLogFile.current?.snapshots.length}
          >
            Download Current Log
          </button>
        </div>
        <LogViewer logs_fpath="test_log.json" mode="playback" />
      </div>
    </div>
  );
};

export default App;
