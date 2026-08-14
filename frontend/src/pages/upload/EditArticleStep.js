import React from "react";
import { Box, Tabs, Tab, FormControlLabel, Checkbox, TextField } from "@mui/material";
import { useTranslation } from "react-i18next";
import ISO6391 from "iso-639-1";
import TabPanel, { a11yProps } from "../../components/TabPanel";

const EditArticleStep = ({
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
        aria-label="edit article tabs"
      >
        {languages.map((lang, idx) => (
          <Tab
            key={lang}
            label={(ISO6391.getNativeName(lang) || lang).toUpperCase()}
            {...a11yProps("edit-article", idx)}
          />
        ))}
      </Tabs>

      {languages.map((lang, idx) => {
        const currentData = languageData[lang] || {};
        return (
          <TabPanel key={lang} value={currentLangIdx} index={idx} idPrefix="edit-article">
            <FormControlLabel
              control={
                <Checkbox
                  checked={currentData.editArticle === true}
                  onChange={(e) => onLanguageDataChange(lang, "editArticle", e.target.checked)}
                  disabled={loading}
                />
              }
              label={t("edit-article")}
            />
            <TextField
              fullWidth
              margin="normal"
              label={t("target-article-name")}
              value={currentData.articleLink || ""}
              onChange={(e) => onLanguageDataChange(lang, "articleLink", e.target.value)}
              disabled={loading || !currentData.editArticle}
              error={!!validationError && currentLangIdx === idx}
              helperText={validationError && currentLangIdx === idx ? t(validationError) : ""}
            />
          </TabPanel>
        );
      })}
    </Box>
  );
};

export default EditArticleStep;
