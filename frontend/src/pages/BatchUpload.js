import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Step,
  StepLabel,
  Stepper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Alert,
  IconButton,
  Paper,
  Tooltip,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";

import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import ISO6391 from "iso-639-1";

import projects from "../utils/projects";
import { properCase, parseSourceUrl } from "../utils/helper";
import backendApi from "../utils/api";

// ─── constants ────────────────────────────────────────────────────────────────
const MAX_FILES = 20;
const POLL_INTERVAL_MS = 2000;

const STEPS = ["Select Target", "Add Files", "Upload"];

// ─── helpers ──────────────────────────────────────────────────────────────────
function makeEmptyRow(id) {
  return { id, srcUrl: "", trFilename: "", _urlError: "" };
}

/** Derive target filename from a wiki source URL (without extension). */
function autoFilename(srcUrl) {
  try {
    const raw = decodeURIComponent(srcUrl).split("/").pop() || "";
    if (raw.includes(":") && raw.includes(".")) {
      return raw.substring(raw.indexOf(":") + 1, raw.lastIndexOf("."));
    }
  } catch (_) {
    // ignore
  }
  return "";
}

// ─── status chip ──────────────────────────────────────────────────────────────
function StatusChip({ status }) {
  const map = {
    success: { label: "Success", color: "success" },
    failed:  { label: "Failed",  color: "error" },
    pending: { label: "Pending", color: "default" },
    uploading: { label: "Uploading…", color: "info" },
  };
  const cfg = map[status] || map.pending;
  return <Chip label={cfg.label} color={cfg.color} size="small" />;
}

// ─── main component ───────────────────────────────────────────────────────────
function BatchUpload() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  // ── target project / language ──
  const [trProject, setTrProject] = useState("");
  const [trLang, setTrLang]       = useState("");
  const [availableLangs, setAvailableLangs] = useState([]);

  // ── file rows ──
  const [rows, setRows] = useState([makeEmptyRow(Date.now())]);

  // ── wizard step ──
  const [activeStep, setActiveStep] = useState(0);

  // ── upload / polling state ──
  const [loading,       setLoading]       = useState(false);
  const [batchProgress, setBatchProgress] = useState(0);
  const [batchMessage,  setBatchMessage]  = useState("");
  const [batchCurrent,  setBatchCurrent]  = useState(0);
  const [batchTotal,    setBatchTotal]    = useState(0);
  const [fileResults,   setFileResults]   = useState([]); // live per-file results
  const [batchDone,     setBatchDone]     = useState(false);
  const [globalError,   setGlobalError]   = useState(null);

  // ── load user preferences ──
  useEffect(() => {
    backendApi.get("/api/preference").then((resp) => {
      const { project, lang } = resp.data.data;
      setTrProject(project || "wikipedia");
      setTrLang(lang || "en");
      setAvailableLangs(projects[project] || []);
    });
  }, []);

  useEffect(() => {
    setAvailableLangs(projects[trProject] || []);
  }, [trProject]);

  // ── row CRUD ──
  const handleAddRow = () => {
    if (rows.length >= MAX_FILES) {
      toast.warning(`Maximum ${MAX_FILES} files per batch`);
      return;
    }
    setRows((prev) => [...prev, makeEmptyRow(Date.now() + Math.random())]);
  };

  const handleRemoveRow = (id) => {
    setRows((prev) => prev.filter((r) => r.id !== id));
  };

  const handleRowChange = (id, field, value) => {
    setRows((prev) =>
      prev.map((r) => {
        if (r.id !== id) return r;
        const updated = { ...r, [field]: value };
        if (field === "srcUrl") {
          updated.trFilename = autoFilename(value);
          updated._urlError  =
            value && !value.includes("/wiki/")
              ? "URL must contain /wiki/"
              : "";
        }
        return updated;
      })
    );
  };

  // ── step validation ──
  const validateStep = () => {
    if (activeStep === 0) {
      if (!trProject || !trLang) {
        toast.error("Please select a target project and language");
        return false;
      }
      return true;
    }

    if (activeStep === 1) {
      if (rows.length === 0) {
        toast.error("Add at least one file");
        return false;
      }
      for (const r of rows) {
        if (!r.srcUrl.trim() || !r.srcUrl.includes("/wiki/")) {
          toast.error(`Invalid source URL: "${r.srcUrl || "(empty)"}"`);
          return false;
        }
        if (!r.trFilename.trim()) {
          toast.error("Each file needs a target filename");
          return false;
        }
      }
      return true;
    }

    return true;
  };

  // ── polling ──
  const pollBatchStatus = useCallback((taskId) => {
    // Optimistic file list while polling
    const pendingResults = rows.map((r) => ({
      file: r.srcUrl.split("/").pop(),
      trFilename: r.trFilename,
      status: "pending",
      wikipage_url: null,
      file_link: null,
      error: null,
    }));
    setFileResults(pendingResults);

    const interval = setInterval(() => {
      backendApi
        .get(`/api/task_status/${taskId}`)
        .then((resp) => {
          const { state, progress, message, current, total, results,
                  succeeded, failed } = resp.data;

          setBatchProgress(progress ?? 0);
          setBatchMessage(message || "");
          if (current != null) setBatchCurrent(current);
          if (total   != null) setBatchTotal(total);

          // Merge live results into our optimistic list
          if (results && results.length > 0) {
            setFileResults((prev) => {
              const merged = [...prev];
              results.forEach((r, i) => {
                if (i < merged.length) merged[i] = r;
              });
              return merged;
            });
          }

          if (state === "SUCCESS") {
            clearInterval(interval);
            setLoading(false);
            setBatchDone(true);
            setBatchProgress(100);
            if (results) setFileResults(results);
          } else if (state === "FAILURE") {
            clearInterval(interval);
            setLoading(false);
            setGlobalError(message || "Batch upload failed");
          }
        })
        .catch(() => {
          // don't stop polling on a transient error
        });
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [rows]);

  // ── submit ──
  const handleSubmit = () => {
    if (!validateStep()) return;

    const payload = {
      items: rows.map((r) => ({
        srcUrl:     r.srcUrl.trim(),
        trFilename: r.trFilename.trim(),
      })),
      trproject: trProject,
      trlang:    trLang,
    };

    setLoading(true);
    setGlobalError(null);
    setBatchProgress(0);
    setBatchTotal(rows.length);
    setActiveStep(2);

    backendApi
      .post("/api/batch_upload", payload)
      .then((resp) => {
        if (resp.status === 202) {
          pollBatchStatus(resp.data.task_id);
        } else {
          setLoading(false);
          setGlobalError("Unexpected response from server");
        }
      })
      .catch((err) => {
        setLoading(false);
        const msg =
          err?.response?.data?.errors?.[0] || err.message || "Batch upload failed";
        setGlobalError(msg);
        toast.error(msg);
      });
  };

  // ── next / back ──
  const handleNext = () => {
    if (!validateStep()) return;
    if (activeStep < STEPS.length - 1) {
      setActiveStep((s) => s + 1);
    }
  };

  const handleBack = () => {
    if (activeStep > 0) setActiveStep((s) => s - 1);
  };

  // ── summary counts ──
  const succeeded = fileResults.filter((r) => r.status === "success").length;
  const failed    = fileResults.filter((r) => r.status === "failed").length;

  // ──────────────────────────────────────────────────────────────────────────
  return (
    <Box sx={{ maxWidth: 800, margin: "auto", padding: 3 }}>
      {/* Page title */}
      <Typography variant="h5" fontWeight={700} mb={2}>
        Batch Upload
      </Typography>

      {/* Stepper */}
      <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {/* Global error */}
      {globalError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {globalError}
        </Alert>
      )}

      {/* ── STEP 0: Target Project / Language ─────────────────────────────── */}
      {activeStep === 0 && (
        <Box>
          <Typography variant="subtitle1" mb={2} color="text.secondary">
            Choose the target wiki where all files will be uploaded.
          </Typography>

          <FormControl fullWidth margin="normal">
            <InputLabel>Target Project</InputLabel>
            <Select
              label="Target Project"
              value={trProject}
              onChange={(e) => setTrProject(e.target.value)}
            >
              {Object.keys(projects).map((p) => (
                <MenuItem key={p} value={p}>
                  {properCase(p)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth margin="normal">
            <InputLabel>Target Language</InputLabel>
            <Select
              label="Target Language"
              value={trLang}
              onChange={(e) => setTrLang(e.target.value)}
            >
              {(availableLangs || []).map((lang) => (
                <MenuItem key={lang} value={lang}>
                  {ISO6391.getNativeName(lang) || lang}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      )}

      {/* ── STEP 1: File List ──────────────────────────────────────────────── */}
      {activeStep === 1 && (
        <Box>
          <Typography variant="subtitle1" mb={2} color="text.secondary">
            Add up to {MAX_FILES} source file URLs. Target filenames are
            auto-filled and can be edited.
          </Typography>

          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: "action.hover" }}>
                  <TableCell sx={{ fontWeight: 700 }}>#</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Source URL</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>
                    Target Filename (no ext.)
                  </TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row, idx) => (
                  <TableRow key={row.id}>
                    <TableCell>{idx + 1}</TableCell>
                    <TableCell sx={{ minWidth: 340 }}>
                      <TextField
                        fullWidth
                        size="small"
                        variant="outlined"
                        placeholder="https://en.wikipedia.org/wiki/File:Example.jpg"
                        value={row.srcUrl}
                        onChange={(e) =>
                          handleRowChange(row.id, "srcUrl", e.target.value)
                        }
                        error={!!row._urlError}
                        helperText={row._urlError}
                      />
                    </TableCell>
                    <TableCell sx={{ minWidth: 200 }}>
                      <TextField
                        fullWidth
                        size="small"
                        variant="outlined"
                        placeholder="Target filename"
                        value={row.trFilename}
                        onChange={(e) =>
                          handleRowChange(row.id, "trFilename", e.target.value)
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Remove row">
                        <span>
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleRemoveRow(row.id)}
                            disabled={rows.length === 1}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Button
            startIcon={<AddCircleOutlineIcon />}
            onClick={handleAddRow}
            disabled={rows.length >= MAX_FILES}
            sx={{ mt: 2 }}
          >
            Add another file ({rows.length}/{MAX_FILES})
          </Button>
        </Box>
      )}

      {/* ── STEP 2: Upload Progress & Results ─────────────────────────────── */}
      {activeStep === 2 && (
        <Box>
          {/* Overall progress bar */}
          <Box mb={3}>
            <Box display="flex" justifyContent="space-between" mb={0.5}>
              <Typography variant="body2" color="text.secondary">
                {loading
                  ? batchMessage || "Processing…"
                  : batchDone
                  ? `Done — ${succeeded} succeeded, ${failed} failed`
                  : "Preparing…"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {batchDone
                  ? `${batchTotal}/${batchTotal}`
                  : `${batchCurrent}/${batchTotal || rows.length}`}{" "}
                files &nbsp;·&nbsp; {batchProgress}%
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={batchProgress}
              sx={{ height: 10, borderRadius: 5 }}
              color={
                batchDone && failed > 0
                  ? "warning"
                  : batchDone
                  ? "success"
                  : "primary"
              }
            />
          </Box>

          {/* Summary chips */}
          {batchDone && (
            <Box display="flex" gap={1} mb={2} flexWrap="wrap">
              <Chip
                label={`Total: ${fileResults.length}`}
                variant="outlined"
              />
              <Chip
                label={`✓ ${succeeded} succeeded`}
                color="success"
                variant="outlined"
              />
              {failed > 0 && (
                <Chip
                  label={`✗ ${failed} failed`}
                  color="error"
                  variant="outlined"
                />
              )}
            </Box>
          )}

          {/* Per-file results table */}
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: "action.hover" }}>
                  <TableCell sx={{ fontWeight: 700 }}>#</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>File</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Target Name</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Link</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {fileResults.map((r, idx) => (
                  <TableRow key={idx}>
                    <TableCell>{idx + 1}</TableCell>
                    <TableCell
                      sx={{
                        maxWidth: 220,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      <Tooltip title={r.file}>
                        <span>{r.file}</span>
                      </Tooltip>
                    </TableCell>
                    <TableCell>{r.trFilename}</TableCell>
                    <TableCell>
                      {loading && r.status === "pending" ? (
                        <CircularProgress size={16} thickness={5} />
                      ) : (
                        <StatusChip status={r.status} />
                      )}
                      {r.status === "failed" && r.error && (
                        <Typography
                          variant="caption"
                          color="error"
                          display="block"
                          sx={{ mt: 0.5 }}
                        >
                          {r.error}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {r.wikipage_url && (
                        <Tooltip title="View on wiki">
                          <IconButton
                            size="small"
                            href={r.wikipage_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            component="a"
                          >
                            <OpenInNewIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Done actions */}
          {batchDone && (
            <Box display="flex" justifyContent="center" gap={2} mt={3}>
              <Button
                variant="outlined"
                onClick={() => {
                  setActiveStep(0);
                  setRows([makeEmptyRow(Date.now())]);
                  setBatchDone(false);
                  setBatchProgress(0);
                  setFileResults([]);
                  setGlobalError(null);
                }}
              >
                Upload Another Batch
              </Button>
              <Button
                variant="contained"
                color="primary"
                onClick={() => navigate("/")}
              >
                Go to Home
              </Button>
            </Box>
          )}
        </Box>
      )}

      {/* ── Navigation buttons ─────────────────────────────────────────────── */}
      {activeStep < STEPS.length - 1 && (
        <Box display="flex" justifyContent="space-between" mt={3}>
          <Button
            onClick={handleBack}
            disabled={activeStep === 0 || loading}
          >
            Back
          </Button>
          {activeStep === STEPS.length - 2 ? (
            <Button
              variant="contained"
              color="primary"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? (
                <>
                  <CircularProgress size={16} sx={{ mr: 1 }} />
                  Uploading…
                </>
              ) : (
                `Upload ${rows.length} file${rows.length !== 1 ? "s" : ""}`
              )}
            </Button>
          ) : (
            <Button
              variant="contained"
              color="primary"
              onClick={handleNext}
              disabled={loading}
            >
              Next
            </Button>
          )}
        </Box>
      )}
    </Box>
  );
}

export default BatchUpload;
