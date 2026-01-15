import { DataGrid } from "@mui/x-data-grid";
import type { GridColDef } from "@mui/x-data-grid";
import { Typography, Box, Button } from "@mui/material";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import { Link } from "react-router-dom";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import FlagIcon from "@mui/icons-material/Flag";
import ReportProblemIcon from "@mui/icons-material/ReportProblem";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";

interface ResultsProps {
    result?: {
        task_id: string;
        metadata: any;
        data: any[];
        status: string;
        error?: string;
    };
    elapsed?: number;
    showSampleBadge?: boolean;
    onStartNew?: () => void;
}

const getLabelIcon = (label: string) => {
    switch (label.toLowerCase()) {
        case "true":
            return <CheckCircleIcon style={{ color: "green", marginRight: 4 }} />;
        case "false":
            return <CancelIcon style={{ color: "red", marginRight: 4 }} />;
        case "unverifiable":
            return <FlagIcon style={{ color: "#b0b0b0", marginRight: 4 }} />;
        case "misleading":
        case "partially true":
        case "misleading/partially true":
            return <ReportProblemIcon style={{ color: "orange", marginRight: 4 }} />;
        default:
            return <HelpOutlineIcon style={{ color: "gold", marginRight: 4 }} />;
    }
};

const ResultsView: React.FC<ResultsProps> = ({ result, elapsed, showSampleBadge, onStartNew }) => {
    // handle error
    const status = result ? result.status ?? "" : "";
    const error = result ? result.error ?? "" : "";
    const metadata = result ? result.metadata ?? "" : "";

    // Count label occurrences
    const labelCounts: Record<string, number> = {};
    const rows = result ? result.data : [];
    rows && rows.forEach((row) => {
        const key = row.label?.toLowerCase() || "other";
        labelCounts[key] = (labelCounts[key] || 0) + 1;
    });
    const total = rows ? rows.length : 0;

    const columns: GridColDef[] = [
        { field: "num", headerName: "Num", width: 40 },
        {
            field: "extracted_claim",
            headerName: "Claim",
            minWidth: 400,
            renderCell: (params) => (
                <Box sx={{ whiteSpace: "normal", wordBreak: "break-word", lineHeight: 1.5 }}>
                    {params.value}
                </Box>
            ),
        },
        {
            field: "label",
            headerName: "Label",
            width: 200,
            renderCell: (params) => (
                <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap" }}>
                    {getLabelIcon(params.value)}
                    <Box sx={{ whiteSpace: "normal", wordBreak: "break-word", lineHeight: 1.5 }}>
                        {params.value}
                    </Box>
                </Box>
            ),
        },
        {
            field: "sources",
            headerName: "Sources (* indicates a reliable domain)",
            flex: 1,
            width: 400,
            renderCell: (params) => (
                <Box sx={{ whiteSpace: "normal", wordBreak: "break-word", lineHeight: 1.5 }}>
                    {Array.isArray(params.value) && params.value.length > 0
                        ? params.value.map((src: string, idx: number) => (
                            <div key={idx}>
                                <a href={src.startsWith("* ") ? src.slice(2) : src} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>{src}</a>
                            </div>
                        ))
                        : null
                    }
                </Box>
            ),
        },
        
    ];

    const handleDownload = () => {
        let url: string | null = null;

        if (showSampleBadge) {
            // /sample-report/1 -> public/sample_report_1.json
            const sampleId = window.location.pathname.split("/").pop();
            if (!sampleId) return;
            url = `/sample_report_${sampleId}.json`;
        } else {
            if (!result?.task_id) return;
            url = `http://127.0.0.1:8000/download/${result.task_id}`;
        }

        const a = document.createElement("a");
        a.href = url;
        a.download = "";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    return (
        <div style={{ width: "100%", paddingTop: "3vh", paddingBottom: "3vh" }}>
            {/* Link to go back */}
            <div style={{ marginBottom: "16px" }}>
                <Link
                    to="/"
                    onClick={() => onStartNew && onStartNew()}
                    style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 4 }}
                >
                    <ArrowBackIcon />
                    <span style={{ fontWeight: "bold" }}>Return to upload page to start a new analysis</span>
                </Link>
            </div>

            {(showSampleBadge || status === "done") &&
                <div>
                    {/* Show Sample Report header if using sample */}
                    {showSampleBadge && (
                        <Typography variant="h5" fontWeight="bold" color="primary" mb={2}>
                            Sample Report
                        </Typography>
                    )}


                    {/* Metadata */}
                    <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" mb={2}>
                        {result?.metadata && (
                            <Box display="flex" gap={4} flexWrap="wrap" mb={2}>
                                {[
                                    ["Finished Time", new Date(metadata.finished_time).toLocaleString()],
                                    ["File Name", metadata.file_name],
                                    ["OpenAI Model", metadata.openai_model],
                                    ["Temperature", metadata.temprature],
                                    ["Perplexity Model", metadata.perplexity_model],
                                ].map(([label, value]) => (
                                    <Typography key={label} variant="body2" color="text.secondary" display="flex" alignItems="center">
                                        <strong>{label}:</strong>&nbsp;{value ?? "-"}
                                    </Typography>
                                ))}
                            </Box>
                        )}
                        <Button
                            variant="outlined"
                            size="small"
                            startIcon={<FileDownloadIcon />}
                            sx={{
                                "&:focus": {
                                    outline: "none",
                                },
                                "&.Mui-focusVisible": {
                                    outline: "none",
                                },
                            }}
                            onClick={handleDownload}
                        >
                            Download Report
                        </Button>
                    </Box>

                    {/* Label statistics */}
                    {total > 0 && (
                        <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" mb={2}>
                            <Box display="flex" gap={2} flexWrap="wrap">
                                {["true", "misleading/partially true", "false", "unverifiable", "other"].map((label) => {
                                    const count = labelCounts[label] || 0;
                                    return (
                                        <Typography key={label} variant="body2" color="text.secondary" display="flex" alignItems="center">
                                            {getLabelIcon(label)}
                                            {label.charAt(0).toUpperCase() + label.slice(1)}: {(count / total * 100).toFixed(1)}%
                                        </Typography>
                                    );
                                })}
                            </Box>

                            {/* Right: elapsed time */}
                            {elapsed !== undefined && !showSampleBadge && (
                                <Typography variant="body2" color="text.secondary">
                                    Analysis completed in <Box component="span" fontWeight="bold">{Math.floor(elapsed / 60)} min {elapsed % 60} sec</Box>
                                </Typography>
                            )}
                        </Box>
                    )}

                    {/* DataGrid */}
                    {rows && (
                        <DataGrid
                            rows={rows.map((row, idx) => ({ id: idx, ...row }))}
                            columns={columns}
                            autoHeight
                            getRowHeight={() => 'auto'}
                            hideFooter
                            sx={{
                                '& .MuiDataGrid-cell': { py: 1 },
                                '& .MuiDataGrid-cellContent': { whiteSpace: 'normal', wordBreak: 'break-word' },
                            }}
                        />
                    )}
                </div>}
            {status === "error" && <div style={{ color: "red" }}>{error}</div>}
            {!showSampleBadge && status !== "done" && status !== "error" && <div>Something went wrong. Please try again.</div>}
        </div>
    );
};

export default ResultsView;
