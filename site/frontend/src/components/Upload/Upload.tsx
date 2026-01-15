import React, { useState, useRef } from "react";
import {
    Box,
    Button,
    TextField,
    Typography,
    CircularProgress,
    Radio,
    Backdrop,
    Menu,
    MenuItem,
    Stack
} from "@mui/material";
import { useNavigate } from "react-router-dom";

interface AnalysisResult {
    data: any[];
    elapsed: number;
}

interface UploadPageProps {
    onSubmit: (result: AnalysisResult) => void;
}

function Upload({ onSubmit }: UploadPageProps) {
    const [file, setFile] = useState<File | null>(null);
    const [rssLink, setRssLink] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [mode, setMode] = useState<"file" | "rss">("file");
    const [elapsed, setElapsed] = useState(0);
    const [apiKeyOpenai, setApiKeyOpenai] = useState("");
    const [apiKeyPerplexity, setApiKeyPerplexity] = useState("");
    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
    const [taskId, setTaskId] = useState<string | null>(null);
    const pollingRef = useRef(true);

    const open = Boolean(anchorEl);
    const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
        setAnchorEl(event.currentTarget);
    };
    const handleClose = () => {
        setAnchorEl(null);
    };

    const timerRef = useRef<number | null>(null);
    const navigate = useNavigate();

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setError("");
        if (e.target.files && e.target.files[0]) setFile(e.target.files[0]);
        else setFile(null);
    };

    const handleRssChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setError("");
        setRssLink(e.target.value);
    };

    const handleModeChange = (value: "file" | "rss") => {
        setMode(value);
        setError("");
    };

    const handleSubmit = async () => {
        setElapsed(0);
        const errors: string[] = [];

        // check input mode
        if (mode === "file" && !file) {
            errors.push("Please upload a podcast file");
        }
        if (mode === "rss" && !rssLink) {
            errors.push("Please input RSS link");
        }

        // check API Key
        if (!apiKeyOpenai) {
            errors.push("OpenAI API Key is required");
        }
        if (!apiKeyPerplexity) {
            errors.push("Perplexity API Key is required");
        }

        // if erro stop submitting
        if (errors.length > 0) {
            setError(errors.join("; "));
            return;
        }

        setError("");
        setLoading(true);
        const start = Date.now();

        // start timer
        timerRef.current = window.setInterval(() => {
            setElapsed(Math.floor((Date.now() - start) / 1000));
        }, 1000);


        try {
            const formData = new FormData();
            if (mode === "file" && file) formData.append("file", file);
            if (mode === "rss" && rssLink) formData.append("rss_url", rssLink);
            if (apiKeyOpenai) formData.append("api_key_openai", apiKeyOpenai);
            if (apiKeyPerplexity) formData.append("api_key_perplexity", apiKeyPerplexity);

            // Start task
            // const response = await fetch("http://127.0.0.1:8000/test-analyze", {
            const response = await fetch("http://127.0.0.1:8000/analyze", {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const text = await response.text();
                throw new Error(text || "API call failed");
            }

            const startData = await response.json();
            const taskId = startData.task_id;
            setTaskId(taskId);

            // Polling for result
            let finalData = null;

            while (pollingRef.current) {
                const res = await fetch(`http://127.0.0.1:8000/result/${taskId}`);
                const json = await res.json();

                if (json.status === "done" || json.status === "error" || json.status === "cancelled") {
                    finalData = json;
                    break;
                } else {
                    await new Promise(r => setTimeout(r, 2000));
                }
            }

            // check if cancelled
            if (!pollingRef.current) return; // if cancelled then don't do the rest

            const totalElapsed = Math.floor((Date.now() - start) / 1000);
            const result = { data: finalData, elapsed: totalElapsed };

            localStorage.setItem("resultData", JSON.stringify(result));
            onSubmit(result);
            navigate("/results");
        } catch (err: any) {
            setError(err.message || "Upload or API call failed");
        } finally {
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
            setLoading(false);
            console.log(elapsed)
        }
    };

    const handleCancelTask = async () => {
        if (!taskId) return;
        pollingRef.current = false;
        navigate("/upload");
        try {
            const res = await fetch(`http://127.0.0.1:8000/cancel/${taskId}`, {
                method: "POST",
            });
            const data = await res.json();
            console.log(data.message);
        } catch (err) {
            console.error(err);
        }
    };

    return (
        <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            minHeight="100vh"
            gap={3}
        >
            <Typography variant="h4" fontWeight="bold" sx={{ marginBottom: "50px" }}>Podcast Factuality Checker</Typography>

            <Box
                display="flex"
                flexDirection="column"
                alignItems="center"
                justifyContent="center"
                gap={2}
                sx={{ width: "70%" }}
            >
                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "center",
                        alignItems: "center",
                        gap: 10,
                    }}
                >
                    <Box
                        sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "flex-start",
                            gap: 2,
                            padding: 1,
                        }}
                    >
                        {/* Upload File */}
                        <Box display="flex" flexDirection="row" alignItems="center" gap={1}>
                            <Radio checked={mode === "file"} onChange={() => handleModeChange("file")} />
                            <Button
                                variant="contained"
                                component="label"
                                disabled={mode !== "file"}
                                sx={{ width: "250px", height: "56px" }}
                                onClick={() => setError("")}
                            >
                                Upload MP3
                                <input type="file" accept="audio/mp3" hidden onChange={handleFileChange} />
                            </Button>
                        </Box>

                        {/* RSS Input */}
                        <Box display="flex" flexDirection="row" alignItems="center" gap={1} sx={{ width: "100%" }}>
                            <Radio checked={mode === "rss"} onChange={() => handleModeChange("rss")} />
                            <TextField
                                fullWidth
                                label="Input RSS link"
                                value={rssLink}
                                onChange={handleRssChange}
                                disabled={mode !== "rss"}
                            />
                        </Box>
                    </Box>
                    <Box
                        sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "flex-start",
                            gap: 2,
                        }}
                    >
                        <Stack spacing={2}>
                            <TextField
                                sx={{ width: 400 }}
                                multiline
                                minRows={6}
                                maxRows={10}
                                label="OpenAI API Key"
                                value={apiKeyOpenai}
                                onChange={(e) => setApiKeyOpenai(e.target.value)}
                                placeholder="Enter your OpenAI API key"
                                required
                            />
                            <TextField
                                sx={{ width: 400 }}
                                multiline
                                minRows={3}
                                maxRows={10}
                                label="Perplexity API Key"
                                value={apiKeyPerplexity}
                                onChange={(e) => setApiKeyPerplexity(e.target.value)}
                                placeholder="Enter your Perplexity API key"
                                required
                            />
                        </Stack>
                    </Box>
                </Box>

                {/* File / RSS messages */}
                <Box minHeight={24}>
                    {mode === "file" && file && (
                        <Typography sx={{ wordBreak: "break-word", whiteSpace: "normal" }}>
                            Selected file: {file.name}
                        </Typography>
                    )}
                </Box>
                <Box minHeight={24}>
                    {error && <Typography color="error">{error}</Typography>}
                </Box>

                <Box display="flex" justifyContent="center" gap={2} sx={{ width: "100%" }} >
                    {/* Submit Analysis */}
                    <Button
                        sx={{ width: "194px", height: "56px" }}
                        variant="contained"
                        color="primary"
                        onClick={handleSubmit}
                        disabled={loading}
                    >
                        Submit Analysis
                    </Button>

                    {/* Sample Report */}
                    <div>
                        <Button
                            aria-controls={open ? 'sample-report-menu' : undefined}
                            aria-haspopup="true"
                            aria-expanded={open ? 'true' : undefined}
                            onClick={handleClick}
                            sx={{
                                width: "194px", height: "56px",
                                "&:focus": {
                                    outline: "none",
                                    boxShadow: "none",
                                },
                            }}
                            variant="outlined"
                            color="secondary"
                        >
                            Sample Report
                        </Button>
                        <Menu
                            id="sample-report-menu"
                            anchorEl={anchorEl}
                            open={open}
                            onClose={handleClose}
                            slotProps={{
                                list: {
                                    'aria-labelledby': 'basic-button',
                                },
                            }}
                        >
                            <MenuItem onClick={() => navigate("/sample-report/1")}>Sample Report 1</MenuItem>
                            <MenuItem onClick={() => navigate("/sample-report/2")}>Sample Report 2</MenuItem>
                            <MenuItem onClick={() => navigate("/sample-report/3")}>Sample Report 3</MenuItem>
                        </Menu>
                    </div>
                </Box>
            </Box>

            {/* Backdrop + Spinner */}
            <Backdrop
                open={loading}
                sx={{
                    zIndex: 1000,
                    color: "#fff",
                    backgroundColor: "rgba(0,0,0,0.75)",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 2,
                }}
            >
                <Box sx={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 2 }}>
                    <CircularProgress color="inherit" size={40} />
                    <Typography variant="h6" fontWeight="bold">
                        Analyzing: {Math.floor(elapsed / 60)}m {elapsed % 60}s
                    </Typography>
                </Box>

                {/* Cancel Task Button */}
                <Button
                    variant="contained"
                    color="error"
                    sx={{
                        mt: 2,
                        "&:focus": {
                            outline: "none",
                            boxShadow: "none",
                        }
                    }}
                    onClick={() => handleCancelTask()}
                >
                    Cancel Task
                </Button>
            </Backdrop>
        </Box>
    );
}

export default Upload;
