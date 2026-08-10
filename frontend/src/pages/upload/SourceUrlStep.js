import React from "react";
import { TextField } from "@mui/material";
import { useTranslation } from "react-i18next";

const SourceUrlStep = ({ sourceUrl, onSourceUrlChange, loading, validationError }) => {
  const { t } = useTranslation();

  return (
    <TextField
      id="source-url-input"
      label={t("source-url-label")}
      placeholder={t("source-url-placeholder")}
      fullWidth
      margin="normal"
      value={sourceUrl}
      onChange={onSourceUrlChange}
      required
      disabled={loading}
      error={!!validationError}
      helperText={validationError ? t(validationError) : ""}
    />
  );
};

export default SourceUrlStep;
