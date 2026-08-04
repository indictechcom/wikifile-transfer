import React, { useState, useEffect, useRef } from "react";
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
  Tabs,
  Tab,
  Checkbox,
  FormControlLabel,
  ListItemText,
} from "@mui/material";

import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import projects from "../utils/projects";
import { properCase, parseSourceUrl } from "../utils/helper";
import ISO6391 from "iso-639-1";
import backendApi from "../utils/api";
import { toast } from "react-toastify";
import axios from "axios";

function Upload() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [availableLanguages, setAvailableLanguages] = useState([]);
  const [error, setError] = useState(null);
  const [showResult, setShowResult] = useState(false);

  const [skipUploadSelection, setSkipUploadSelection] = useState(false);

  const [sourceUrl, setSourceUrl] = useState("");
  const [project, setProject] = useState("");
  
  const [languages, setLanguages] = useState([]);
  const [languageData, setLanguageData] = useState({});
  const [activeTabs, setActiveTabs] = useState({ 2: 0, 3: 0, 4: 0 });
  const [successTab, setSuccessTab] = useState(0);

  const [pendingTasks, setPendingTasks] = useState({});
  const [uploadResults, setUploadResults] = useState({});
  const pollIntervalRef = useRef(null);

  const currentLangIdx = activeTabs[activeStep] || 0;
  const currentLang = languages[currentLangIdx] || "";
  const currentData = languageData[currentLang] || {};

  const pendingLangs = Object.keys(pendingTasks);
  
  const validResultTab = Math.min(successTab, Math.max(0, languages.length - 1));
  const currentResultLang = languages[validResultTab] || "";

  const steps = [
    t("enter-source-url"),
    t("select-project-and-language"),
    t("name-of-target-file"),
    t("add-template"),
    t("edit-article"),
  ];

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const handleLanguageDataChange = (lang, field, value) => {
    setLanguageData((prev) => ({
      ...prev,
      [lang]: { ...prev[lang], [field]: value },
    }));
  };

  const handleNext = async () => {
    const isValid = await isStepValid();
    if (activeStep === 0 && isValid === true && skipUploadSelection) {
      setActiveStep(2);
      return;
    }

    if (isValid === true) {
      setError(null);
      setActiveStep((prevStep) => prevStep + 1);
    } else if (isValid !== true && isValid.length > 0) {
      toast.error(t(isValid));
    }
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleFinish = async () => {
    const isValid = await isStepValid();
    if (isValid !== true && isValid.length > 0) {
      toast.error(t(isValid));
      return;
    }

    const payload = {
      srcUrl: sourceUrl,
      trproject: project,
      tasks: languages.map((lang) => ({
        lang: lang,
        trfilename: languageData[lang]?.targetFileName || "",
        addTemplate: languageData[lang]?.addTemplate !== false, 
        pageContent: languageData[lang]?.pageContent || "",
        editArticle: languageData[lang]?.editArticle === true,
        articleLink: languageData[lang]?.articleLink || "",
      })),
    };

    try {
      setLoading(true);
      const response = await backendApi.post("/api/upload_multi", payload);

      if (response.status === 200) {
        const results = {};
        languages.forEach((lang) => {
          results[lang] = { status: "SUCCESS", data: response.data.data[lang] || response.data.data };
        });
        setUploadResults(results);
        setLoading(false);
        setShowResult(true);
        toast.success(t("upload-success"));
      } else if (response.status === 202) {
        const tasks = response.data.tasks || {};
        setPendingTasks(tasks);

        const initialResults = {};
        languages.forEach((lang) => {
          initialResults[lang] = { status: "PENDING" };
        });
        setUploadResults(initialResults);

        pollTaskStatus(tasks);
      }
    } catch (error) {
      setLoading(false);
      setError(t("upload-error"));
      toast.error(`${t("upload-error")}: ${error}`);
    }
  };

  const pollTaskStatus = (initialTasks) => {
    let currentPendingTasks = { ...initialTasks };

    pollIntervalRef.current = setInterval(async () => {
      const pendingKeys = Object.keys(currentPendingTasks);

      if (pendingKeys.length === 0) {
        clearInterval(pollIntervalRef.current);
        setLoading(false);
        setError(null);
        toast.success(t("uploads-completed"));
        setShowResult(true);
        return;
      }

      for (const lang of pendingKeys) {
        const taskId = currentPendingTasks[lang];
        try {
          const response = await backendApi.get(`/api/task_status/${taskId}`);
          const { status, result, error } = response.data;

          if (status === "SUCCESS") {
            setUploadResults((prev) => ({
              ...prev,
              [lang]: { status: "SUCCESS", data: result },
            }));
            delete currentPendingTasks[lang];
          } else if (status === "PARTIAL") {
            setUploadResults((prev) => ({
              ...prev,
              [lang]: { status: "PARTIAL", data: result, warnings: error },
            }));
            delete currentPendingTasks[lang];
          } else if (status === "FAILURE") {
            setUploadResults((prev) => ({
              ...prev,
              [lang]: { status: "FAILURE", error: error || t("task-failed-processing") },
            }));
            delete currentPendingTasks[lang];
          }
        } catch (pollError) {
          toast.error(`${t("poll-error")}: ${pollError}`);
        }
      }

      setPendingTasks({ ...currentPendingTasks });
    }, 2000);
  };

  const isStepValid = async () => {
    switch (activeStep) {
      case 0:
        if (sourceUrl.trim() !== "" && sourceUrl.includes("/wiki/")) {
          return true;
        } else {
          return "enter-valid-source-url";
        }

      case 1:
        if (
          project !== "" &&
          languages.length > 0 &&
          languages.length <= 3 &&
          projects.hasOwnProperty(project) &&
          languages.every((lang) => projects[project].includes(lang))
        ) {
          return true;
        } else {
          return "enter-valid-project-language";
        }

      case 2:
        const sourceFileExt = sourceUrl.substring(sourceUrl.lastIndexOf(".") + 1);

        for (const lang of languages) {
          const trfilename = languageData[lang]?.targetFileName;
          if (!trfilename) return "enter-target-filename";

          const apiUrl = `https://${lang}.${project}.org/w/api.php?action=query&titles=File:${encodeURIComponent(
            trfilename
          )}.${sourceFileExt}&format=json&origin=*`;

          try {
            const response = await axios.get(apiUrl);
            const pages = response.data.query.pages;
            const pageId = Object.keys(pages)[0];

            if (pageId !== "-1") {
              return "target-file-name-exist";
            } else if (Object.keys(pages[pageId]).includes("invalidreason")) {
              return "target-file-name-invalid";
            }
          } catch (err) {
            return "target-file-name-invalid";
          }
        }
        return true;

      case 3:
        return true;

      case 4:
        // validation logic for step 5
        for (const lang of languages) {
          if (languageData[lang]?.editArticle) {
            // TODO: check with wikimedia API if image param exists in template with empty url
            return "validation-failed";
          }
        }
        return true;
      default:
        return true;
    }
  };

  useEffect(() => {
    let nameWithoutExtension = "";
    if (sourceUrl && sourceUrl.includes("/")) {
      const fileNameWithExtension = sourceUrl.split("/").pop() || "";
      if (fileNameWithExtension) {
        nameWithoutExtension =
          fileNameWithExtension.includes(":") && fileNameWithExtension.includes(".")
            ? fileNameWithExtension.substring(
                fileNameWithExtension.indexOf(":") + 1,
                fileNameWithExtension.lastIndexOf(".")
              )
            : "";
      }
    }

    const sourceUrlObj = parseSourceUrl(sourceUrl);

    setLanguageData((prev) => {
      const newData = { ...prev };
      let stateChanged = false;

      languages.forEach((lang) => {
        if (!newData[lang]) {
          newData[lang] = {};
        }

        if (nameWithoutExtension && !newData[lang].targetFileName) {
          newData[lang].targetFileName = nameWithoutExtension;
          stateChanged = true;
        }

        if (newData[lang].pageContent === undefined && sourceUrlObj) {
          newData[lang].pageContent = ""; 
          stateChanged = true;

          backendApi
            .get("/api/get_wikitext", {
              params: {
                src_lang: sourceUrlObj.srcLang,
                src_project: sourceUrlObj.srcProject,
                src_filename: sourceUrlObj.srcFileName,
                tr_lang: lang,
              },
            })
            .then((response) => {
              if (response.data.wikitext) {
                handleLanguageDataChange(lang, "pageContent", response.data.wikitext);
              }
            })
            .catch(() => {
              // Failure to fetch wikitext
            });
        }
      });

      return stateChanged ? newData : prev;
    });
  }, [sourceUrl, languages]);

  useEffect(() => {
    setAvailableLanguages(projects[project] || []);
  }, [project]);

  useEffect(() => {
    backendApi.get("/api/preference").then((response) => {
      setProject(response.data.data.project);
      if (response.data.data.lang) {
        setLanguages([response.data.data.lang]);
      }
      setAvailableLanguages(projects[response.data.data.project] || []);
      setSkipUploadSelection(response.data.data.skip_upload_selection);
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
        <Typography color="error" variant="body2" sx={{ textAlign: "center", mt: 2 }}>
          {error}
        </Typography>
      )}

      {showResult ? (
        <Box textAlign="center">
          {pendingLangs.length > 0 ? (
            <Box mt={5} mb={5}>
              <CircularProgress />
              <Typography mt={2}>
                {/* Changed to show exact progress numbers */}
                {t("processing-uploads")} ({languages.length - pendingLangs.length} / {languages.length})
              </Typography>
            </Box>
          ) : (
            <>
              {/* Changed Tabs to iterate overall selected languages and apply status colors */}
              <Tabs value={validResultTab} onChange={(e, val) => setSuccessTab(val)} centered>
                {languages.map((lang, idx) => (
                  <Tab 
                    key={lang} 
                    label={(ISO6391.getNativeName(lang) || lang).toUpperCase()} 
                    value={idx} 
                    sx={{
                      color:
                        uploadResults[lang]?.status === "SUCCESS"
                          ? "success.main"
                          : uploadResults[lang]?.status === "PARTIAL"
                          ? "warning.main"
                          : uploadResults[lang]?.status === "FAILURE"
                          ? "error.main"
                          : "inherit",
                    }}
                  />
                ))}
              </Tabs>

              {currentResultLang && uploadResults[currentResultLang] && (
                <Box mt={2}>
                  {/* FAILURE PANEL: Show this strictly when language has failed */}
                  {uploadResults[currentResultLang].status === "FAILURE" ? (
                    <Box mt={2} p={3} border="1px solid #f5c6cb" borderRadius={2} bgcolor="#f8d7da">
                      <Typography variant="h6" fontWeight="bold" color="error">
                        {t("upload-failed")}
                      </Typography>
                      <Typography variant="body1" color="error" mt={1}>
                        {uploadResults[currentResultLang].error || t("task-failed-processing")}
                      </Typography>
                    </Box>
                  ) : (
                    <>
                      {/* PARTIAL WARNING PANEL: Render warnings for partial success */}
                      {uploadResults[currentResultLang].status === "PARTIAL" && (
                        <Box mt={2} mb={3} p={2} border="1px solid #ffeeba" borderRadius={2} bgcolor="#fff3cd">
                          <Typography variant="subtitle1" fontWeight="bold" sx={{ color: "warning.main" }}>
                            {t("partial-success")}
                          </Typography>
                          <Typography variant="body2" sx={{ color: "warning.main" }}>
                            {uploadResults[currentResultLang].warnings || uploadResults[currentResultLang].error || t("partial-warning-default")}
                          </Typography>
                        </Box>
                      )}

                      {/* Article Edit Status Label for Success/Partial Screen */}
                      {languageData[currentResultLang]?.editArticle &&
                        uploadResults[currentResultLang].data?.article_edit_success !== undefined && (
                          <Box mt={2} mb={3} p={2} border="1px solid #ccc" borderRadius={2} bgcolor="#f9f9f9">
                            <Typography variant="subtitle1" fontWeight="bold">
                              Article Update Target
                            </Typography>
                            <Typography variant="body2" sx={{ mb: 1 }}>
                              <a
                                href={languageData[currentResultLang].articleLink}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                {languageData[currentResultLang].articleLink}
                              </a>
                            </Typography>
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight: "bold",
                                color: uploadResults[currentResultLang].data.article_edit_success
                                  ? "green"
                                  : "error.main",
                              }}
                            >
                              Status:{" "}
                              {uploadResults[currentResultLang].data.article_edit_success
                                ? "Successfully updated!"
                                : "Failed or No changes made."}
                            </Typography>
                          </Box>
                        )}

                      {uploadResults[currentResultLang].data && (
                        <>
                          <img
                            src={uploadResults[currentResultLang].data.file_link}
                            alt="Uploaded File"
                            style={{ maxWidth: "100%" }}
                            height={380}
                            width={260}
                          />
                          <Box display="flex" justifyContent="center" mt={2}>
                            <TextField
                              style={{ width: "650px" }}
                              value={(() => {
                                const fileName = decodeURIComponent(uploadResults[currentResultLang].data.wikipage_url).split("/").pop();
                                return fileName.includes(":") ? fileName.substring(fileName.indexOf(":") + 1) : fileName;
                              })()}
                              disabled={true}
                              slotProps={{
                                input: {
                                  endAdornment: (
                                    <Button
                                      variant="contained"
                                      color="primary"
                                      onClick={() => {
                                        const fileName = decodeURIComponent(uploadResults[currentResultLang].data.wikipage_url).split("/").pop();
                                        const nameOnly = fileName.includes(":") ? fileName.substring(fileName.indexOf(":") + 1) : fileName;
                                        navigator.clipboard.writeText(nameOnly);
                                      }}
                                    >
                                      {t("copy")}
                                    </Button>
                                  ),
                                },
                              }}
                            />
                          </Box>
                          <Box display="flex" justifyContent="center" mt={2}>
                            <Button
                              variant="contained"
                              color="primary"
                              href={uploadResults[currentResultLang].data.wikipage_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {t("view-wiki-page")}
                            </Button>
                            <Button variant="contained" color="secondary" sx={{ ml: 2 }} onClick={() => navigate("/")}>
                              {t("go-back-to-home")}
                            </Button>
                          </Box>
                        </>
                      )}
                    </>
                  )}
                </Box>
              )}
            </>
          )}
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
                  onChange={(e) => {
                    setProject(e.target.value);
                    setLanguages([]);
                  }}
                  disabled={loading}
                >
                  {Object.keys(projects).map((proj) => (
                    <MenuItem key={proj} value={proj}>
                      {properCase(proj)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl fullWidth margin="normal">
                <InputLabel>{t("select-language")}</InputLabel>
                <Select
                  multiple
                  label={t("select-language")}
                  value={languages}
                  onChange={(e) => {
                    const val = e.target.value;
                    const selected = typeof val === "string" ? val.split(",") : val;
                    if (selected.length <= 3) {
                      setLanguages(selected);
                    } else {
                      toast.error(t("max-languages"));
                    }
                  }}
                  renderValue={(selected) => selected.map((l) => ISO6391.getNativeName(l) || l).join(", ")}
                  disabled={loading}
                >
                  {availableLanguages.map((lang) => (
                    <MenuItem key={lang} value={lang}>
                      <Checkbox checked={languages.indexOf(lang) > -1} />
                      <ListItemText primary={ISO6391.getNativeName(lang) || lang} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </>
          )}

          {activeStep === 2 && (
            <Box textAlign="center">
              <Tabs
                value={currentLangIdx}
                onChange={(e, val) => setActiveTabs((prev) => ({ ...prev, [activeStep]: val }))}
                centered
              >
                {languages.map((lang, idx) => (
                  <Tab key={lang} label={(ISO6391.getNativeName(lang) || lang).toUpperCase()} value={idx} />
                ))}
              </Tabs>
              <Box mt={2}>
                <TextField
                  label={`${t("target-file-name-label")} (${currentLang})`}
                  placeholder={t("target-file-name-placeholder")}
                  fullWidth
                  margin="normal"
                  value={currentData.targetFileName || ""}
                  onChange={(e) => handleLanguageDataChange(currentLang, "targetFileName", e.target.value)}
                  required
                  disabled={loading}
                />
              </Box>
              {loading && (
                <Box display="flex" justifyContent="center" mt={2}>
                  <CircularProgress />
                </Box>
              )}
            </Box>
          )}

          {activeStep === 3 && (
            <Box textAlign="center">
              <Tabs
                value={currentLangIdx}
                onChange={(e, val) => setActiveTabs((prev) => ({ ...prev, [activeStep]: val }))}
                centered
              >
                {languages.map((lang, idx) => (
                  <Tab key={lang} label={(ISO6391.getNativeName(lang) || lang).toUpperCase()} value={idx} />
                ))}
              </Tabs>
              <Box mt={2}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={currentData.addTemplate !== false}
                      onChange={(e) => handleLanguageDataChange(currentLang, "addTemplate", e.target.checked)}
                    />
                  }
                  label={t("add-template")}
                />
                <TextField
                  label={t("add-template")}
                  multiline
                  rows={10}
                  fullWidth
                  margin="normal"
                  value={currentData.pageContent || ""}
                  onChange={(e) => handleLanguageDataChange(currentLang, "pageContent", e.target.value)}
                  disabled={currentData.addTemplate === false || loading}
                />
              </Box>
            </Box>
          )}

          {activeStep === 4 && (
            <Box textAlign="center">
              <Tabs
                value={currentLangIdx}
                onChange={(e, val) => setActiveTabs((prev) => ({ ...prev, [activeStep]: val }))}
                centered
              >
                {languages.map((lang, idx) => (
                  <Tab key={lang} label={(ISO6391.getNativeName(lang) || lang).toUpperCase()} value={idx} />
                ))}
              </Tabs>
              <Box mt={2}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={currentData.editArticle === true}
                      onChange={(e) => handleLanguageDataChange(currentLang, "editArticle", e.target.checked)}
                    />
                  }
                  label={t("edit-article")}
                />
                <TextField
                  label={t("target-article-link")}
                  fullWidth
                  margin="normal"
                  value={currentData.articleLink || ""}
                  onChange={(e) => handleLanguageDataChange(currentLang, "articleLink", e.target.value)}
                  disabled={currentData.editArticle !== true || loading}
                />
              </Box>
            </Box>
          )}

          {activeStep <= steps.length - 1 && (
            <Box display="flex" justifyContent="space-between" mt={2}>
              <Box>
                {/* Back button strictly isolated to step 1 and 2 (0-indexed) per your requirement */}
                {(activeStep === 1 || activeStep === 2) && (
                  <Button disabled={loading} onClick={handleBack}>
                    {t("back")}
                  </Button>
                )}
              </Box>
              <Button
                variant="contained"
                color="primary"
                onClick={activeStep === steps.length - 1 ? handleFinish : handleNext}
                disabled={loading}
              >
                {activeStep === steps.length - 1 ? t("upload-file-to-target-wiki") : t("next")}
              </Button>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}

export default Upload;