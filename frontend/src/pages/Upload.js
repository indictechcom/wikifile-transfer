import React, { useReducer, useEffect, useRef, useCallback } from "react";
import { Box, Stepper, Step, StepLabel, Typography, Button } from "@mui/material";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import axios from "axios";

import { uploadReducer, initialUploadState } from "./upload/uploadReducer";
import SourceUrlStep from "./upload/SourceUrlStep";
import ProjectLanguageStep from "./upload/ProjectLanguageStep";
import TargetFileNameStep from "./upload/TargetFileNameStep";
import TemplateStep from "./upload/TemplateStep";
import EditArticleStep from "./upload/EditArticleStep";
import UploadResultsView from "./upload/UploadResultsView";

import projects from "../utils/projects";
import { parseSourceUrl } from "../utils/helper";
import backendApi from "../utils/api";

function Upload() {
  const { t } = useTranslation();

  const [state, dispatch] = useReducer(uploadReducer, initialUploadState);
  const pollIntervalRef = useRef(null);
  const fetchedWikitextRef = useRef(new Set());

  const availableLanguages = projects[state.project] || [];
  const currentLangIdx = state.activeTabs[state.activeStep] || 0;

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

  // Fetch initial preferences
  useEffect(() => {
    let ignore = false;
    backendApi.get("/api/preference").then((response) => {
      if (!ignore) {
        dispatch({
          type: "INIT_PREFERENCES",
          payload: {
            project: response.data.data.project,
            languages: response.data.data.lang ? [response.data.data.lang] : [],
            skipUploadSelection: response.data.data.skip_upload_selection,
          }
        });
      }
    }).catch(() => {
      // Preferences fetch failed — continue with defaults
    });
    return () => { ignore = true; };
  }, []);

  // Sync language data when source URL or languages change
  useEffect(() => {
    let ignore = false;
    let nameWithoutExtension = "";
    if (state.sourceUrl && state.sourceUrl.includes("/")) {
      const fileNameWithExtension = state.sourceUrl.split("/").pop() || "";
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

    const sourceUrlObj = parseSourceUrl(state.sourceUrl);

    dispatch({
      type: "BATCH_INIT_LANGUAGE_DATA",
      payload: {
        languages: state.languages,
        defaultFileName: nameWithoutExtension
      }
    });

    state.languages.forEach((lang) => {
      const fetchKey = `${state.sourceUrl}__${lang}`;
      if (!fetchedWikitextRef.current.has(fetchKey) && sourceUrlObj) {
        fetchedWikitextRef.current.add(fetchKey);
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
            if (!ignore && response.data.wikitext) {
              dispatch({
                type: "UPDATE_LANGUAGE_DATA",
                payload: { lang, field: "pageContent", value: response.data.wikitext }
              });
            }
          })
          .catch(() => {
            // Failure to fetch wikitext — non-critical
          });
      }
    });

    return () => { ignore = true; };
  }, [state.sourceUrl, state.languages]);

  const isStepValid = async () => {
    switch (state.activeStep) {
      case 0:
        if (state.sourceUrl.trim() !== "" && state.sourceUrl.includes("/wiki/")) {
          return true;
        }
        return "enter-valid-source-url";

      case 1:
        if (
          state.project !== "" &&
          state.languages.length > 0 &&
          state.languages.length <= 3 &&
          projects.hasOwnProperty(state.project) &&
          state.languages.every((lang) => projects[state.project].includes(lang))
        ) {
          return true;
        }
        return "enter-valid-project-language";

      case 2:
        const sourceFileExt = state.sourceUrl.substring(state.sourceUrl.lastIndexOf(".") + 1);

        for (const lang of state.languages) {
          const trfilename = state.languageData[lang]?.targetFileName;
          if (!trfilename) return "enter-target-filename";

          const apiUrl = `https://${lang}.${state.project}.org/w/api.php?action=query&titles=File:${encodeURIComponent(
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
        for (const lang of state.languages) {
          if (state.languageData[lang]?.editArticle) {
            if (!state.languageData[lang]?.articleLink || state.languageData[lang].articleLink.trim() === "") {
              return "enter-valid-article-name";
            }
          }
        }
        return true;
      default:
        return true;
    }
  };

  const handleNext = async () => {
    dispatch({ type: "SET_VALIDATION_ERROR", payload: null });
    const isValid = await isStepValid();
    if (state.activeStep === 0 && isValid === true && state.skipUploadSelection) {
      dispatch({ type: "SKIP_TO_STEP", payload: 2 });
      return;
    }

    if (isValid === true) {
      dispatch({ type: "SET_ERROR", payload: null });
      dispatch({ type: "NEXT_STEP" });
    } else if (isValid !== true && isValid.length > 0) {
      dispatch({ type: "SET_VALIDATION_ERROR", payload: isValid });
      toast.error(t(isValid));
    }
  };

  const handleBack = () => {
    dispatch({ type: "PREV_STEP" });
  };

  const handleEditArticle = async (lang) => {
    try {
      dispatch({ type: "EDIT_ARTICLE_START", payload: lang });
      const payload = {
        articleName: state.languageData[lang].articleLink,
        content: state.editableWikitexts[lang],
        lang: lang,
        project: state.project,
      };
      
      const response = await backendApi.post("/api/edit_article", payload);
      if (response.status === 200 && response.data.success) {
        dispatch({ type: "EDIT_ARTICLE_SUCCESS", payload: lang });
        toast.success(t("article-edit-success") || "Article edited successfully!");
      } else {
        toast.error(response.data.errors?.[0] || "Failed to edit article");
        dispatch({ type: "EDIT_ARTICLE_FAILURE", payload: lang });
      }
    } catch (error) {
      toast.error("An error occurred while editing the article");
      dispatch({ type: "EDIT_ARTICLE_FAILURE", payload: lang });
    } finally {
      dispatch({ type: "EDIT_ARTICLE_END", payload: lang });
    }
  };

  const pollTaskStatus = useCallback((initialTasks) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    let currentPendingTasks = { ...initialTasks };

    pollIntervalRef.current = setInterval(async () => {
      const pendingKeys = Object.keys(currentPendingTasks);

      if (pendingKeys.length === 0) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        dispatch({ type: "SET_LOADING", payload: false });
        dispatch({ type: "SET_ERROR", payload: null });
        toast.success(t("uploads-completed"));
        return;
      }

      for (const lang of pendingKeys) {
        const taskId = currentPendingTasks[lang];
        try {
          const response = await backendApi.get(`/api/task_status/${taskId}`);
          const { status, result, error, progress } = response.data;

          if (status === "SUCCESS") {
            dispatch({
              type: "UPDATE_UPLOAD_RESULT",
              payload: { lang, result: { status: "SUCCESS", data: result } }
            });
            if (result && result.wikitext_fetch_success && result.wikitext) {
              dispatch({
                type: "UPDATE_EDITABLE_WIKITEXT",
                payload: { lang, text: result.wikitext }
              });
            }
            delete currentPendingTasks[lang];
          } else if (status === "PROGRESS") {
            dispatch({
              type: "UPDATE_UPLOAD_RESULT",
              payload: { lang, result: { status: "PROGRESS", progress: progress || 0 } }
            });
          } else if (status === "PARTIAL") {
            dispatch({
              type: "UPDATE_UPLOAD_RESULT",
              payload: { lang, result: { status: "PARTIAL", data: result, warnings: error } }
            });
            if (result && result.wikitext_fetch_success && result.wikitext) {
              dispatch({
                type: "UPDATE_EDITABLE_WIKITEXT",
                payload: { lang, text: result.wikitext }
              });
            }
            delete currentPendingTasks[lang];
          } else if (status === "FAILURE") {
            dispatch({
              type: "UPDATE_UPLOAD_RESULT",
              payload: { lang, result: { status: "FAILURE", error: error || t("task-failed-processing") } }
            });
            delete currentPendingTasks[lang];
          }
        } catch (pollError) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          dispatch({ type: "SET_LOADING", payload: false });
          dispatch({ type: "SET_ERROR", payload: t("poll-error") });
          toast.error(t("poll-error"));
          return;
        }
      }

      dispatch({ type: "SET_PENDING_TASKS", payload: { ...currentPendingTasks } });
    }, 2000);
  }, [t]);

  const handleFinish = async () => {
    dispatch({ type: "SET_VALIDATION_ERROR", payload: null });
    const isValid = await isStepValid();
    if (isValid !== true && isValid.length > 0) {
      dispatch({ type: "SET_VALIDATION_ERROR", payload: isValid });
      toast.error(t(isValid));
      return;
    }

    const payload = {
      srcUrl: state.sourceUrl,
      trproject: state.project,
      tasks: state.languages.map((lang) => ({
        lang: lang,
        trfilename: state.languageData[lang]?.targetFileName || "",
        addTemplate: state.languageData[lang]?.addTemplate !== false, 
        pageContent: state.languageData[lang]?.pageContent || "",
        editArticle: state.languageData[lang]?.editArticle === true,
        articleLink: state.languageData[lang]?.articleLink || "",
      })),
    };

    try {
      dispatch({ type: "SET_LOADING", payload: true });

      const initialTasks = {};
      const initialResults = {};
      state.languages.forEach((lang) => {
        initialTasks[lang] = "sync_uploading";
        initialResults[lang] = { status: "PROGRESS" };
      });
      
      dispatch({
        type: "UPLOAD_ASYNC_START",
        payload: { tasks: initialTasks, initialResults }
      });

      const response = await backendApi.post("/api/upload_multi", payload);

      if (response.status === 200) {
        const results = {};
        const newEditable = {};
        
        state.languages.forEach((lang) => {
          const langData = response.data.data[lang] || response.data.data;
          results[lang] = { status: "SUCCESS", data: langData };
          if (langData.wikitext_fetch_success && langData.wikitext) {
            newEditable[lang] = langData.wikitext;
          }
        });
        
        dispatch({
          type: "UPLOAD_SYNC_SUCCESS",
          payload: { results, editableWikitexts: newEditable }
        });
        toast.success(t("upload-success"));
      } else if (response.status === 202) {
        const tasks = response.data.tasks || {};
        
        const initialResults = {};
        state.languages.forEach((lang) => {
          initialResults[lang] = { status: "PENDING", progress: 0 };
        });

        dispatch({
          type: "UPLOAD_ASYNC_START",
          payload: { tasks, initialResults }
        });
        pollTaskStatus(tasks);
      }
    } catch (error) {
      const errorMessage = error.response?.data?.errors?.[0] || error.message || String(error);
      const results = {};
      
      state.languages.forEach((lang) => {
        if (error.response?.data?.lang && error.response.data.lang !== lang) {
          results[lang] = { status: "FAILURE", error: t("task-failed-processing") };
        } else {
          results[lang] = { status: "FAILURE", error: errorMessage };
        }
      });

      dispatch({
        type: "UPLOAD_COMPLETED",
        payload: { results, editableWikitexts: {} }
      });
    }
  };

  const handleTabChange = useCallback((e, val) => {
    dispatch({
      type: "SET_ACTIVE_TAB",
      payload: { step: state.activeStep, index: val }
    });
  }, [state.activeStep]);

  const handleLanguageDataChange = useCallback((lang, field, value) => {
    dispatch({
      type: "UPDATE_LANGUAGE_DATA",
      payload: { lang, field, value }
    });
  }, []);

  return (
    <Box sx={{ maxWidth: 650, margin: "auto", padding: 3 }}>
      {!state.showResult && (
        <Box component="nav" aria-label="Upload steps stepper">
          <Stepper 
            activeStep={state.activeStep} 
            alternativeLabel
            sx={{
              "& .MuiStepIcon-root.Mui-completed": {
                color: "success.main",
              }
            }}
          >
            {steps.map((label, index) => {
              const stepProps = {};
              const labelProps = {};
              if (index === 3 || index === 4) {
                labelProps.optional = (
                  <Typography variant="caption">{t("optional")}</Typography>
                );
              }
              return (
                <Step key={label} {...stepProps}>
                  <StepLabel {...labelProps}>{label}</StepLabel>
                </Step>
              );
            })}
          </Stepper>
        </Box>
      )}

      {state.error && (
        <Typography color="error" variant="body2" sx={{ textAlign: "center", mt: 2 }}>
          {state.error}
        </Typography>
      )}

      {state.showResult ? (
        <Box textAlign="center">
          <UploadResultsView
            project={state.project}
            languages={state.languages}
            languageData={state.languageData}
            pendingTasks={state.pendingTasks}
            uploadResults={state.uploadResults}
            editableWikitexts={state.editableWikitexts}
            onEditableWikitextChange={(lang, text) => dispatch({ type: "UPDATE_EDITABLE_WIKITEXT", payload: { lang, text } })}
            editingState={state.editingState}
            articleEditSuccess={state.articleEditSuccess}
            onEditArticle={handleEditArticle}
            successTab={state.successTab}
            onSuccessTabChange={(e, val) => dispatch({ type: "SET_SUCCESS_TAB", payload: val })}
          />
        </Box>
      ) : (
        <Box>
          {state.activeStep === 0 && (
            <SourceUrlStep
              sourceUrl={state.sourceUrl}
              onSourceUrlChange={(e) => dispatch({ type: "SET_SOURCE_URL", payload: e.target.value })}
              loading={state.loading}
              validationError={state.validationError}
            />
          )}

          {state.activeStep === 1 && (
            <ProjectLanguageStep
              project={state.project}
              languages={state.languages}
              availableLanguages={availableLanguages}
              onProjectChange={(e) => dispatch({ type: "SET_PROJECT", payload: e.target.value })}
              onLanguagesChange={(newLanguages) => dispatch({ type: "SET_LANGUAGES", payload: newLanguages })}
              loading={state.loading}
            />
          )}

          {state.activeStep === 2 && (
            <TargetFileNameStep
              languages={state.languages}
              languageData={state.languageData}
              currentLangIdx={currentLangIdx}
              onTabChange={handleTabChange}
              onLanguageDataChange={handleLanguageDataChange}
              loading={state.loading}
              validationError={state.validationError}
            />
          )}

          {state.activeStep === 3 && (
            <TemplateStep
              languages={state.languages}
              languageData={state.languageData}
              currentLangIdx={currentLangIdx}
              onTabChange={handleTabChange}
              onLanguageDataChange={handleLanguageDataChange}
              loading={state.loading}
            />
          )}

          {state.activeStep === 4 && (
            <EditArticleStep
              languages={state.languages}
              languageData={state.languageData}
              currentLangIdx={currentLangIdx}
              onTabChange={handleTabChange}
              onLanguageDataChange={handleLanguageDataChange}
              loading={state.loading}
              validationError={state.validationError}
            />
          )}

          {/* Nav buttons */}
          <Box display="flex" justifyContent="space-between" mt={4}>
            {(state.activeStep === 1 || state.activeStep === 2) && (
              <Button
                disabled={state.loading}
                onClick={handleBack}
              >
                {t("back")}
              </Button>
            )}
            {state.activeStep === steps.length - 1 ? (
              <Button
                variant="contained"
                color="primary"
                onClick={handleFinish}
                disabled={state.loading}
              >
                {t("upload-file-to-target-wiki")}
              </Button>
            ) : (
              <Button
                variant="contained"
                color="primary"
                onClick={handleNext}
                disabled={state.loading}
              >
                {t("next")}
              </Button>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
}

export default Upload;