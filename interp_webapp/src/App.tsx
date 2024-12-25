import React, { useState } from "react";
import express from "express";
import cors from "cors";
import bodyParser from "body-parser";

const server = express();
server.use(cors());
server.use(bodyParser.json({ limit: "50mb" }));

const App = () => {
  const [imageData, setImageData] = useState("");

  server.post("/image", (req, res) => {
    const { image } = req.body;
    setImageData(image);
    res.json({ status: "success" });
  });

  server.listen(3001, () => {
    console.log("Server running on port 3001");
  });

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-2xl mx-auto">
        {imageData ? (
          <img
            src={`data:image/jpeg;base64,${imageData}`}
            alt="Uploaded content"
            className="w-full rounded-lg shadow-lg"
          />
        ) : (
          <div className="text-gray-500">
            Send POST to /image with {"{ image: 'base64string' }"}
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
