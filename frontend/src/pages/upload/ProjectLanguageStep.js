import React from "react";
import { FormControl, InputLabel, Select, MenuItem, Autocomplete, TextField } from "@mui/material";
import { useTranslation } from "react-i18next";
import projects from "../../utils/projects";
import { properCase } from "../../utils/helper";
import ISO6391 from "iso-639-1";
import { toast } from "react-toastify";

const ProjectLanguageStep = ({
  project,
  languages,
  availableLanguages,
  onProjectChange,
  onLanguagesChange,
  loading
}) => {
  const { t } = useTranslation();

  const handleLanguageChange = (event, newValue) => {
    if (newValue.length > 3) {
      toast.error(t("max-languages"));
      return;
    }
    onLanguagesChange(newValue);
  };

  return (
    <>
      <FormControl fullWidth margin="normal">
        <InputLabel id="project-select-label">{t("select-project")}</InputLabel>
        <Select
          id="project-select"
          labelId="project-select-label"
          label={t("select-project")}
          value={project}
          onChange={onProjectChange}
          disabled={loading}
        >
          {Object.keys(projects).map((proj) => (
            <MenuItem key={proj} value={proj}>
              {properCase(proj)}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Autocomplete
          id="language-autocomplete"
          multiple
          disableCloseOnSelect
          limitTags={3}
          options={availableLanguages}
          value={languages}
          onChange={handleLanguageChange}
          getOptionLabel={(option) => ISO6391.getNativeName(option) || option}
          disabled={loading || !project}
          renderInput={(params) => (
            <TextField
              {...params}
              variant="outlined"
              label={t("select-language")}
              placeholder={t("select-language")}
            />
          )}
        />
    </>
  );
};

export default ProjectLanguageStep;
