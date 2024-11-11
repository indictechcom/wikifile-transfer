import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import projects from "../utils/projects";
import { properCase } from "../utils/helper";
import ISO6391 from "iso-639-1";
import backendApi from "../utils/api";
import { toast } from "react-toastify";

function Preferences() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [availableLanguages, setAvailableLanguages] = useState([]);

  const [project, setProject] = useState("wikipedia");
  const [language, setLanguage] = useState("en");
  const [skipUploadSelection, setSkipUploadSelection] = useState(false);

  const handleSave = () => {
    const payload = {
      project,
      lang: language,
      skip_upload_selection: skipUploadSelection,
    };

    backendApi.post("/api/preference", payload).then((resp) => {
      if (resp.status === 200 && resp.data.success === true) {
        toast(t("preferences-saved"), { type: "success" });
      }
    });
  };

  const handleCancel = () => {
    navigate("/");
  };

  useEffect(() => {
    setAvailableLanguages(projects[project]);
  }, [project]);

  // Fetch user preferences and set the state
  useEffect(() => {
    backendApi.get("/api/preference").then((response) => {
      setProject(response.data.data.project);
      setLanguage(response.data.data.lang);
      setSkipUploadSelection(response.data.data.skip_upload_selection);

      // Set available languages based on the project
      setAvailableLanguages(projects[response.data.data.project]);
    });
  }, []);

  return (
    <Box sx={{ padding: 3, maxWidth: 500, margin: "auto" }}>
      <Typography variant="h4" gutterBottom>
        {t("my-preferences")}
      </Typography>
      <FormControl fullWidth margin="normal">
        <InputLabel>{t("select-project")}</InputLabel>
        <Select
          label={t("select-project")}
          value={project}
          onChange={(e) => setProject(e.target.value)}
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
        >
          {availableLanguages.map((lang) => (
            <MenuItem key={lang} value={lang}>
              {ISO6391.getNativeName(lang) || lang}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControlLabel
        label={t("skip-selection")}
        control={
          <Checkbox
            checked={skipUploadSelection}
            onChange={() => setSkipUploadSelection(!skipUploadSelection)}
          />
        }
      />
      <Box
        sx={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}
      >
        <Button variant="outlined" color="primary" onClick={handleSave}>
          Save
        </Button>
        <Button variant="outlined" color="error" onClick={handleCancel}>
          Cancel
        </Button>
      </Box>
    </Box>
  );
}

export default Preferences;
