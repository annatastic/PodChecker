import React from "react";
import {
    Box,
    Button,
    Typography,
    Menu,
    MenuItem
} from "@mui/material";
import { useNavigate } from "react-router-dom";

interface AnalysisResult {
    data: any[];
    elapsed: number;
}

interface UploadPageProps {
    onSubmit: (result: AnalysisResult) => void;
}

function Upload({ }: UploadPageProps) {
    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
   
    const open = Boolean(anchorEl);
    const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
        setAnchorEl(event.currentTarget);
    };
    const handleClose = () => {
        setAnchorEl(null);
    };

    const navigate = useNavigate();


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
                    variant="contained"
                    // color="secondary"
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

            <Typography variant="body1" sx={{ marginTop: "40px", maxWidth: 500, textAlign: "center" }}>
                For the full Podcast Factuality Checker experience, visit us on{" "}
                <a href="https://github.com/annatastic/PodChecker" target="_blank" rel="noopener noreferrer"
                    style={{ color: "inherit", textDecoration: "underline" }}>
                    GitHub
                </a>{" "}
                to access the complete code and features.
            </Typography>
        </Box>
    );
}

export default Upload;
