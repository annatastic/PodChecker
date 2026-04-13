import { useState } from "react";
import { Upload } from "./components/Upload";
import { Results, SampleReport } from "./components/Results";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Box } from "@mui/material";

function App() {
    const [resultData, setResultData] = useState<{ data: any[]; elapsed: number } | null>(() => {
        const stored = localStorage.getItem("resultData");
        return stored ? JSON.parse(stored) : null;
    });

    return (
        <Box
            sx={{
                width: "90vw",
                minHeight: "100vh",
                margin: 0,
                padding: 0,
            }}
        >
            <BrowserRouter>
                <Routes>
                    <Route
                        path="/"
                        element={<Upload onSubmit={(result) => setResultData(result)} />}
                    />
                    <Route
                        path="/results"
                        element={
                            resultData ? (
                                <Results
                                    data={resultData.data}
                                    elapsed={resultData.elapsed}
                                    onStartNew={() => {
                                        localStorage.removeItem("resultData");
                                        setResultData(null);
                                    }}
                                />
                            ) : (
                                <Results data={[]} />
                            )
                        }
                    />
                    {/* Sample result – always show sample */}
                    <Route path="/sample-report/:id" element={<SampleReport />} />
                    <Route path="*" element={<Navigate to="/" />} />
                </Routes>
            </BrowserRouter>
        </Box>
    );
}

export default App;
