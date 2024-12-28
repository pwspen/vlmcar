import { LogFile, DataSnapshot } from "./types"; // Assuming you've moved interfaces to a types.ts file

export const loadLogFile = async (
  filename: string
): Promise<DataSnapshot[]> => {
  try {
    // Dynamically import the JSON file
    const logFile: LogFile = await import(`./${filename}`);

    // Validate the structure
    if (!logFile.snapshots || !Array.isArray(logFile.snapshots)) {
      throw new Error("Invalid log file format");
    }

    // Ensure all snapshots have required fields
    const validSnapshots = logFile.snapshots.map((snapshot, index) => {
      if (!snapshot.timestamp) {
        console.warn(
          `Snapshot ${index} missing timestamp, using index as timestamp`
        );
        snapshot.timestamp = index;
      }
      if (!snapshot.id) {
        snapshot.id = index;
      }
      if (!snapshot.data) {
        snapshot.data = {};
      }
      return snapshot;
    });

    return validSnapshots;
  } catch (error) {
    console.error("Error loading log file:", error);
    return [];
  }
};
