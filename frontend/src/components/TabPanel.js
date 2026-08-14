import React from "react";
import { Box } from "@mui/material";

function TabPanel({ children, value, index, idPrefix = "tab", ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`${idPrefix}-tabpanel-${index}`}
      aria-labelledby={`${idPrefix}-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
}

export function a11yProps(prefix, index) {
  return {
    id: `${prefix}-tab-${index}`,
    "aria-controls": `${prefix}-tabpanel-${index}`,
  };
}

export default TabPanel;
