import React from "react";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";
import { useTranslation, Trans } from "react-i18next";

const Footer = () => {
  const { t } = useTranslation();
  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static" color="primary">
        <Toolbar>
          <Typography
            variant="body2"
            color="inherit"
            sx={{ flexGrow: 1, textAlign: "center" }}
          >
            &copy; {new Date().getFullYear()} {t("site-title")}.{" "}
            <Trans
              i18nKey="source-code"
              values={{ github: t("github") }}
              components={[
                <Link
                  href="https://github.com/indictechcom/wikifile-transfer"
                  target="_blank"
                  color="inherit"
                  underline="always"
                />
              ]}
            />{" "}
            ({t('license')}).
          </Typography>
        </Toolbar>
      </AppBar>
    </Box>
  );
};

export default Footer;
