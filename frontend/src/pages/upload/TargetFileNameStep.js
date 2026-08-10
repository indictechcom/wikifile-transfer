import React from "react";
import { Box, Tabs, Tab, TextField, CircularProgress } from "@mui/material";
import { useTranslation } from "react-i18next";
import ISO6391 from "iso-639-1";
import TabPanel, { a11yProps } from "../../components/TabPanel";

const TargetFileNameStep = ({
  languages,
  languageData,
  currentLangIdx,
  onTabChange,
  onLanguageDataChange,
  loading,
  validationError
}) => {
  const { t } = useTranslation();

  return (
    <Box textAlign="center">
      <Tabs
        value={currentLangIdx}
        onChange={onTabChange}
        centered
        aria-label="target file name tabs"
      >
        {languages.map((lang, idx) => (
          <Tab
            key={lang}
            label={(ISO6391.getNativeName(lang) || lang).toUpperCase()}
            {...a11yProps("target-filename", idx)}
          />
        ))}
      </Tabs>
      
      {languages.map((lang, idx) => {
        const currentData = languageData[lang] || {};
        return (
          <TabPanel key={lang} value={currentLangIdx} index={idx} idPrefix="target-filename">
            <TextField
              id={`target-filename-${lang}`}
              label={`${t("target-file-name-label")} (${lang})`}
              placeholder={t("target-file-name-placeholder")}
              fullWidth
              margin="normal"
              value={currentData.targetFileName || ""}
              onChange={(e) => onLanguageDataChange(lang, "targetFileName", e.target.value)}
              required
              disabled={loading}
              error={!!validationError && currentLangIdx === idx}
              helperText={validationError && currentLangIdx === idx ? t(validationError) : ""}
            />
          </TabPanel>
        );
      })}

      {loading && (
        <Box display="flex" justifyContent="center" mt={2}>
          <CircularProgress />
        </Box>
      )}
    </Box>
  );
};

export default TargetFileNameStep;
