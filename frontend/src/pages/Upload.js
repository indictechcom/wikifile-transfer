import React, { useState, useEffect } from "react";
import {
  Box,
  TextField,
  Select,
  MenuItem,
  Button,
  Stepper,
  Step,
  StepLabel,
  Typography,
  FormControl,
  InputLabel,
  CircularProgress,
} from "@mui/material";

import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import projects from "../utils/projects";
import { properCase } from "../utils/helper";
import ISO6391 from "iso-639-1";
import backendApi from "../utils/api";
import { toast } from "react-toastify";
import { parseSourceUrl } from "../utils/helper";
import axios from "axios";

function Upload() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [availableLanguages, setAvailableLanguages] = useState([]);
  const [error, setError] = useState(null);
  const [showResult, setShowResult] = useState(false);

  const [sourceUrl, setSourceUrl] = useState("");
  const [project, setProject] = useState("");
  const [language, setLanguage] = useState("");
  const [targetFileName, setTargetFileName] = useState("");
  const [uploadStatus, setUploadStatus] = useState({ type: null, data: null });
  const [pageContent, setPageContent] = useState("");

  const steps = [
    t("enter-source-url"),
    t("select-project-and-language"),
    t("name-of-target-file"),
    t("add-template"),
  ];

  const handleNext = () => {
    if (activeStep === 2 && isStepValid()) {
      handleUpload();
    } else if (isStepValid()) {
      setError(null);
      setActiveStep((prevStep) => prevStep + 1);
    } else {
      toast.error(t("complete-all-fields"));
    }
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleUpload = () => {
    const payload = {
      srcUrl: sourceUrl,
      trproject: project,
      trlang: language,
      trfilename: targetFileName,
    };

    setLoading(true);
    backendApi
      .post("/api/upload", payload)
      .then((response) => {
        if (response.status === 202) {
          const taskId = response.data.task_id;
          pollTaskStatus(taskId);
        } else if (response.status === 200) {
          setUploadStatus({ type: "success", data: response.data.data });
          setLoading(false);
          setError(null);
          setActiveStep((prevStep) => prevStep + 1);
        }
      })
      .catch((error) => {
        setLoading(false);
        setError(t("upload-error"));
        toast.error(`${t("upload-error")}: ${error}`);
      });
  };

  const pollTaskStatus = (taskId) => {
    const interval = setInterval(() => {
      backendApi
        .get(`/api/task_status/${taskId}`)
        .then((response) => {
          const { status, result, error } = response.data;

          if (status === "SUCCESS") {
            clearInterval(interval);
            setUploadStatus({ type: "success", data: result });
            setLoading(false);
            setError(null);
            setActiveStep((prevStep) => prevStep + 1);
          } else if (status === "FAILURE") {
            clearInterval(interval);
            setLoading(false);
            setError(error || t("task-failed-processing"));
          }
        })
        .catch((pollError) => {
          toast.error(`${t("poll-error")}: ${pollError}`);
        });
    }, 2000);
  };

  const handleFinishWithoutEdit = () => {
    setError(null);
    setShowResult(true);
  };

  const handleFinishWithEdit = () => {
    const payload = {
      content: pageContent,
      targetUrl: uploadStatus.data.wikipage_url,
    };

    setLoading(true);
    setError(null);

    backendApi
      .post("/api/edit_page", payload)
      .then((response) => {
        if (response.status === 200) {
          setError(null);
          setShowResult(true);
        } else {
          setError(t("edit-error"));
        }
        setLoading(false);
      })
      .catch((error) => {
        setLoading(false);
        setError(t("edit-error"));
        toast.error(`${t("edit-error")}: ${error}`);
      });
  };

  const isStepValid = () => {
    switch (activeStep) {
      case 0:
        return sourceUrl.trim() !== "" && sourceUrl.includes("/wiki/");
  
      case 1:
        return (
          project !== "" &&
          language !== "" &&
          projects.hasOwnProperty(project) &&
          projects[project].includes(language)
        );
  
      case 2:
        const fileNamePattern = /^[a-zA-Z0-9_()]+$/;;
        return targetFileName.trim() !== "" && fileNamePattern.test(targetFileName);
  
      default:
        return true;
    }
  };


  const fetchPageContent = async (srcLang, srcProject, srcFileName) => {
    try {
      const srcEndpoint = `https://${srcLang}.${srcProject}.org/w/api.php`;
      const params = {
        action: "query",
        format: "json",
        prop: "revisions",
        titles: srcFileName,
        formatversion: "2",
        rvprop: "content",
        rvslots: "main",
        origin: "*",
      };
  
      const response = await axios.get(srcEndpoint, { params });
      const pageData = response.data.query.pages;
  
      if (pageData && pageData[0]?.revisions?.[0]?.slots?.main?.content) {
        const content = pageData[0].revisions[0].slots.main.content;
        setPageContent(content);
      } else {
        toast.error(t("content-not-found"));
      }
    } catch (error) {
      toast.error(t("fetch-content-error"));
    }
  };
  
  useEffect(() => {
    if (uploadStatus.type === "success" && uploadStatus.data) {
      const sourceUrlObj = parseSourceUrl(sourceUrl);
      if (sourceUrlObj) {
        const { srcLang, srcProject, srcFileName } = sourceUrlObj;

        fetchPageContent(srcLang, srcProject, srcFileName);
      }
    }
  }, [uploadStatus, sourceUrl]);

  useEffect(() => {
    if (sourceUrl) {
      if (sourceUrl.includes("/")) {
        const fileNameWithExtension = sourceUrl.split("/").pop() || "";
  
        if (fileNameWithExtension) {
          const fileName = fileNameWithExtension.split(":")?.[1]?.split(".")?.[0];
          if (fileName) {
            setTargetFileName(fileName);
          }
        } else {
          setTargetFileName("");
        }
      } else {
        setTargetFileName("");
      }
    } else {
      setTargetFileName("");
    }
  }, [sourceUrl]);

  useEffect(() => {
    setAvailableLanguages(projects[project]);
  }, [project]);

  useEffect(() => {
    backendApi.get("/api/preference").then((response) => {
      setProject(response.data.data.project);
      setLanguage(response.data.data.lang);
      setAvailableLanguages(projects[response.data.data.project]);
    });
  }, []);

  return (
    <Box sx={{ maxWidth: 650, margin: "auto", padding: 3 }}>
      {!showResult && (
        <Stepper activeStep={activeStep} alternativeLabel>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
      )}

      {error && (
        <Typography
          color="error"
          variant="body2"
          sx={{ textAlign: "center", mt: 2 }}
        >
          {error}
        </Typography>
      )}

      {showResult ? (
        <Box textAlign="center">
          <Box mt={2}>
            <img
              src={uploadStatus.data.file_link}
              alt="Uploaded File"
              style={{ maxWidth: "100%" }}
              height={380}
              width={260}
            />
            <Box display="flex" justifyContent="center" mt={2}>
              <Button
                variant="contained"
                color="primary"
                href={uploadStatus.data.wikipage_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("view-wiki-page")}
              </Button>
              <Button
                variant="contained"
                color="secondary"
                sx={{ ml: 2 }}
                onClick={() => navigate("/")}
              >
                {t("go-back-to-home")}
              </Button>
            </Box>
          </Box>
        </Box>
      ) : activeStep === steps.length - 1 ? (
        <Box textAlign="center">
          <TextField
            label={t("source-url-label")}
            multiline
            rows={10}
            fullWidth
            margin="normal"
            value={pageContent}
            onChange={(e) => setPageContent(e.target.value)}
          />
          <Box display="flex" justifyContent="center" mt={2}>
            <Button
              variant="contained"
              onClick={handleFinishWithoutEdit}
              disabled={loading}
              sx={{ backgroundColor: 'red', '&:hover': { backgroundColor: 'darkred' } }}
            >
              {t("finish-without-edit")}
            </Button>
            <Button
              color="primary"
              variant="contained"
              onClick={handleFinishWithEdit}
              disabled={loading}
              sx={{ ml: 2 }}
            >
              {t("finish-with-edit")}
            </Button>
          </Box>
        </Box>
      ) : (
        <Box>
          {activeStep === 0 && (
            <TextField
              label={t("source-url-label")}
              placeholder={t("source-url-placeholder")}
              fullWidth
              margin="normal"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              required
              disabled={loading}
            />
          )}

          {activeStep === 1 && (
            <>
              <FormControl fullWidth margin="normal">
                <InputLabel>{t("select-project")}</InputLabel>
                <Select
                  label={t("select-project")}
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                  disabled={loading}
                >
                  {Object.keys(projects).map((project) => (
                    <MenuItem key={project} value={project}>
                      {properCase(project)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl fullWidth margin="normal">
                <InputLabel>{t("select-language")}</InputLabel>
                <Select
                  label={t("select-language")}
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  disabled={loading}
                >
                  {availableLanguages.map((lang) => (
                    <MenuItem key={lang} value={lang}>
                      {ISO6391.getNativeName(lang) || lang}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </>
          )}

          {activeStep === 2 && (
            <>
              <TextField
                label={t("target-file-name-label")}
                placeholder={t("target-file-name-placeholder")}
                fullWidth
                margin="normal"
                value={targetFileName}
                onChange={(e) => setTargetFileName(e.target.value)}
                required
                disabled={loading}
              />
              {loading && (
                <Box display="flex" justifyContent="center" mt={2}>
                  <CircularProgress />
                </Box>
              )}
            </>
          )}

          {activeStep < steps.length - 1 && (
            <Box display="flex" justifyContent="space-between" mt={2}>
              <Button
                disabled={activeStep === 0 || loading}
                onClick={handleBack}
              >
                {t("back")}
              </Button>
              <Button
                variant="contained"
                color="primary"
                onClick={handleNext}
                disabled={loading}
              >
                {activeStep === steps.length - 2
                  ? t("upload-file-to-target-wiki")
                  : t("next")}
              </Button>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}

export default Upload;
