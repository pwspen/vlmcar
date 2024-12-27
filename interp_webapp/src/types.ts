export interface WebSocketData {
  image?: string;
  timestamp?: number;
  [key: string]: any;
}

export interface DataSnapshot {
  id: number;
  image?: string;
  data: Record<string, any>;
  timestamp: number;
}

export interface LogFile {
  startTime: number;
  snapshots: DataSnapshot[];
}

export interface LogSnapshotProps {
  snapshot: DataSnapshot;
  formatTimestamp?: (timestamp: number) => string;
}

export interface LogViewerProps {
  snapshots?: DataSnapshot[];
  mode?: "live" | "playback";
  playbackDelay?: number; // milliseconds between snapshots during playback
  logs_fpath?: string; // Path to the JSON log file
}
