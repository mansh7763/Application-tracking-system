import React, { useState, ChangeEvent, FormEvent } from "react";
import "./PromptInput.css";

interface FileData {
  name: string;
  type: string;
  content: string;
}

interface Output {
  status?: string;
  message?: string;
  response?: string;
}

const PromptInput: React.FC = () => {
  const [jobDesc, setJobDesc] = useState<string>("");
  const [prompt, setPrompt] = useState<string>("");
  const [shortlistedCand, setShortlistedCand] = useState<string>("");
  const [chatMessage, setChatMessage] = useState<string>("");
  const [chatHistory, setChatHistory] = useState<string[]>([]);
  const [output, setOutput] = useState<Output | null>(null);
  const [initialSubmitted, setInitialSubmitted] = useState<boolean>(false);
  const [files, setFiles] = useState<File[]>([]);
  const [checkpoints, setCheckpoints] = useState<string[]>([]);

  const handleInitialSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (files.length === 0) {
      setOutput({ status: "error", message: "Please select files to upload" });
      setCheckpoints((prevCheckpoints) => [
        ...prevCheckpoints,
        "No files selected.",
      ]);
      return;
    }

    try {
      const filePromises = files.map((file) => {
        return new Promise<FileData>((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            resolve({
              name: file.name,
              type: file.type,
              content: (reader.result as string).split(",")[1],
            });
          };
          reader.onerror = reject;
          reader.readAsDataURL(file);
        });
      });

      const fileData = await Promise.all(filePromises);
      setCheckpoints((prevCheckpoints) => [
        ...prevCheckpoints,
        "Files converted to base64.",
      ]);

      const response = await fetch("http://localhost:5000/api/upload", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          jobDesc,
          files: fileData,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }

      const data = await response.json();
      setOutput(data);
      setInitialSubmitted(true);
      setFiles([]);
      setCheckpoints((prevCheckpoints) => [
        ...prevCheckpoints,
        "Files uploaded successfully.",
      ]);
    } catch (error) {
      console.error(
        "Error uploading files and submitting initial data:",
        error
      );
      setOutput({
        status: "error",
        message: "Error uploading files and submitting initial data",
      });
      setCheckpoints((prevCheckpoints) => [
        ...prevCheckpoints,
        "Error during file upload.",
      ]);
    }
  };

  const handlePromptSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch("http://localhost:5000/api/prompt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt,
          shortlistedCand,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }

      const data = await response.json();
      setOutput(data);
      setCheckpoints((prevCheckpoints) => [
        ...prevCheckpoints,
        "Prompt submitted successfully.",
      ]);
    } catch (error) {
      console.error("Error submitting prompt data:", error);
      setOutput({ status: "error", message: "Error submitting prompt data" });
      setCheckpoints((prevCheckpoints) => [
        ...prevCheckpoints,
        "Error during prompt submission.",
      ]);
    }
  };

  const handleChatSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch("http://localhost:5000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: chatMessage,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }

      const data = await response.json();
      setChatHistory((prevHistory) => [
        ...prevHistory,
        `User: ${chatMessage}`,
        `Assistant: ${data.response}`,
      ]);
      setChatMessage("");
    } catch (error) {
      console.error("Error submitting chat message:", error);
      setOutput({ status: "error", message: "Error submitting chat message" });
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    setFiles(selectedFiles);
    setCheckpoints((prevCheckpoints) => [
      ...prevCheckpoints,
      `${selectedFiles.length} file(s) selected.`,
    ]);
  };

  const parseTableData = (data: string) => {
    const rows = data.trim().split("\n");
    const headers = rows[1].split("|").map((header) => header.trim());
    const tableData = rows.slice(3).map((row) =>
      row
        .split("|")
        .map((cell) => cell.trim())
        .slice(1, -1)
    );
    return { headers, tableData };
  };

  return (
    <div
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
      }}
    >
      <div className="container1">
        <form onSubmit={handleInitialSubmit}>
          <div className="input-group">
            <input
              type="file"
              onChange={handleFileChange}
              accept=".pdf,.doc,.docx,.txt"
              multiple
              required
            />
            <input
              className="desc"
              type="text"
              value={jobDesc}
              onChange={(e) => setJobDesc(e.target.value)}
              placeholder="Enter the Job Description"
              required
            />
            <button type="submit">Submit Initial Data</button>
          </div>
        </form>
      </div>

      {initialSubmitted && (
        <div className="container2">
          <form onSubmit={handlePromptSubmit}>
            <div className="prompt-group">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Enter your prompt"
                required
              />
              <input
                type="number"
                value={shortlistedCand}
                onChange={(e) => setShortlistedCand(e.target.value)}
                placeholder="Enter the number of candidates you'll proceed with"
                required
              />
              <button type="submit">Proceed</button>
            </div>
          </form>
        </div>
      )}

      {output && (
        <div className="container output">
          {output.status && (
            <div>
              <h2>Status:</h2>
              <p>{output.status}</p>
            </div>
          )}
          {output.message && (
            <div>
              <h2>Message:</h2>
              <p>{output.message}</p>
            </div>
          )}
          {output.response && (
            <div>
              <h2>Response:</h2>
              <table>
                <thead>
                  <tr>
                    {parseTableData(output.response).headers.map(
                      (header, index) => (
                        <th key={index}>{header}</th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {parseTableData(output.response).tableData.map(
                    (row, rowIndex) => (
                      <tr key={rowIndex}>
                        {row.map((cell, cellIndex) => (
                          <td key={cellIndex}>{cell}</td>
                        ))}
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="container checkpoints">
        <h2>Checkpoints:</h2>
        <ul>
          {checkpoints.map((checkpoint, index) => (
            <li key={index}>{checkpoint}</li>
          ))}
        </ul>
      </div>

      <div className="container chat">
        <h2>Chat with Assistant</h2>
        <div className="chat-history">
          {chatHistory.map((message, index) => (
            <p key={index}>{message}</p>
          ))}
        </div>
        <form onSubmit={handleChatSubmit}>
          <input
            type="text"
            value={chatMessage}
            onChange={(e) => setChatMessage(e.target.value)}
            placeholder="Enter your message"
            required
          />
          <button type="submit">Send</button>
        </form>
      </div>
    </div>
  );
};

export default PromptInput;
