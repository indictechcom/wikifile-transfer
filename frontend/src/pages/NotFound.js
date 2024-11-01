// NotFound.js
import React from "react";
import { Typography, Button, Box } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useTranslation } from 'react-i18next';

function NotFound() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleBackToHome = () => {
    navigate("/");
  };

  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      textAlign="center"
      padding={3}
    >
      <Typography variant="h1" color="error" gutterBottom>
        404
      </Typography>
      <Typography variant="h5" gutterBottom>
        {t("404-heading")}
      </Typography>
      <Typography variant="body1" color="textSecondary" marginBottom={3}>
        {t("404-text")}
      </Typography>
      <Button variant="contained" color="primary" onClick={handleBackToHome}>
        {t("back-to-home")}
      </Button>
    </Box>
  );
}

export default NotFound;
