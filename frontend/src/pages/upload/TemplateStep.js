import React from "react";
import { Box, Tabs, Tab, FormControlLabel, Checkbox, TextField } from "@mui/material";
import { useTranslation } from "react-i18next";
import ISO6391 from "iso-639-1";
import TabPanel, { a11yProps } from "../../components/TabPanel";

const TemplateStep = ({
  languages,
  languageData,
  currentLangIdx,
  onTabChange,
  onLanguageDataChange,
  loading
}) => {
  const { t } = useTranslation();

  return (
    <Box textAlign="center">
      <Tabs
        value={currentLangIdx}
        onChange={onTabChange}
        centered
        aria-label="template tabs"
      >
        {languages.map((lang, idx) => (
          <Tab
            key={lang}
            label={(ISO6391.getNativeName(lang) || lang).toUpperCase()}
            {...a11yProps("template", idx)}
          />
        ))}
      </Tabs>

      {languages.map((lang, idx) => {
        const currentData = languageData[lang] || {};
        return (
          <TabPanel key={lang} value={currentLangIdx} index={idx} idPrefix="template">
            <FormControlLabel
              control={
                <Checkbox
                  checked={currentData.addTemplate !== false}
                  onChange={(e) => onLanguageDataChange(lang, "addTemplate", e.target.checked)}
                  disabled={loading}
                />
              }
              label={t("add-template")}
            />
            <TextField
              multiline
              rows={10}
              fullWidth
              margin="normal"
              label={t("add-template")}
              value={currentData.pageContent || ""}
              onChange={(e) => onLanguageDataChange(lang, "pageContent", e.target.value)}
              disabled={loading || currentData.addTemplate === false}
            />
          </TabPanel>
        );
      })}
    </Box>
  );
};

export default TemplateStep;
