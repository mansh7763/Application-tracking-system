import React, { useState } from "react";
import "./PromptInput.css";

const PromptInput = () => {
  const [jobDesc, setJobDesc] = useState("");
  const [category, setCategory] = useState("");
  const [prompt, setPrompt] = useState("");
  const [shortlistedCand, setShortlistedCand] = useState("");
  const [output, setOutput] = useState(null); // Changed to null initially
  const [initialSubmitted, setInitialSubmitted] = useState(false); // Changed to boolean

  const handleInitialSubmit = async (e) => {
    e.preventDefault();
    const response = await fetch("http://localhost:5000/api/prior_info", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ jobDesc, category }),
    });
    const data = await response.json();
    setOutput(data);
    setInitialSubmitted(true); // Set initialSubmitted to true after submission
  };

  const handlePromptSubmit = async (e) => {
    e.preventDefault();
    const response = await fetch("http://localhost:5000/api/prompt", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt,
        shortlistedCand,
        category,
      }),
    });
    const data = await response.json();
    setOutput(data);
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
              className="desc"
              type="text"
              value={jobDesc}
              onChange={(e) => setJobDesc(e.target.value)}
              placeholder="Enter the Job Description"
              required
            />
            <input
              className="category"
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="Enter the category"
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
              <p>{output.response}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PromptInput;
