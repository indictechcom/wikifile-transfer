import React from "react";
import {
  Box, Typography, Stack, Card, CardHeader, CardContent, CardActions,
  LinearProgress, Tabs, Tab, TextField, Button, Alert, Link, CircularProgress,
  InputAdornment
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ISO6391 from "iso-639-1";
import TabPanel, { a11yProps } from "../../components/TabPanel";

const UploadResultsView = ({
  project,
  languages,
  languageData,
  pendingTasks,
  uploadResults,
  editableWikitexts,
  onEditableWikitextChange,
  editingState,
  articleEditSuccess,
  onEditArticle,
  successTab,
  onSuccessTabChange
}) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  
  const pendingLangs = Object.keys(pendingTasks);
  const validResultTab = Math.min(successTab, Math.max(0, languages.length - 1));

  if (pendingLangs.length > 0) {
    return (
      <Box mt={2} mb={5} textAlign="left">
        <Typography variant="h6" gutterBottom>
          {t("processing-uploads")} ({languages.length - pendingLangs.length} / {languages.length})
        </Typography>
        <Stack spacing={2} mt={3}>
          {languages.map((lang) => {
            const res = uploadResults[lang] || { status: "PENDING", progress: 0 };
            const langName = (ISO6391.getNativeName(lang) || lang).toUpperCase();
            
            return (
              <Card key={lang} variant="outlined" sx={{ p: 2, display: "flex", alignItems: "center" }}>
                <Box sx={{ width: '100%', mr: 1 }}>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="subtitle2" fontWeight="bold">
                      {langName}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {res.status === "PENDING" && "Waiting in queue..."}
                      {res.status === "PROGRESS" && (res.progress !== undefined ? `Uploading... ${res.progress}%` : "Uploading...")}
                      {res.status === "SUCCESS" && <span style={{ color: "green" }}>Completed</span>}
                      {res.status === "PARTIAL" && <span style={{ color: "orange" }}>Partial Success</span>}
                      {res.status === "FAILURE" && <span style={{ color: "red" }}>Failed</span>}
                    </Typography>
                  </Box>
                  {res.status === "FAILURE" ? (
                    <Typography variant="caption" color="error">
                      {res.error}
                    </Typography>
                  ) : res.status === "SUCCESS" || res.status === "PARTIAL" ? (
                    <LinearProgress aria-label={`Progress for ${langName}`} variant="determinate" value={100} color={res.status === "SUCCESS" ? "success" : "warning"} />
                  ) : (
                    <LinearProgress aria-label={`Progress for ${langName}`} variant={res.status === "PROGRESS" && res.progress !== undefined ? "determinate" : "indeterminate"} value={res.progress || 0} />
                  )}
                </Box>
              </Card>
            );
          })}
        </Stack>
      </Box>
    );
  }

  return (
    <>
      <Tabs value={validResultTab} onChange={onSuccessTabChange} centered aria-label="upload results tabs">
        {languages.map((lang, idx) => (
          <Tab 
            key={lang} 
            label={(ISO6391.getNativeName(lang) || lang).toUpperCase()} 
            {...a11yProps("result", idx)}
            sx={{
              color:
                uploadResults[lang]?.status === "SUCCESS" ? "success.main"
                  : uploadResults[lang]?.status === "PARTIAL" ? "warning.main"
                  : uploadResults[lang]?.status === "FAILURE" ? "error.main"
                  : "inherit",
            }}
          />
        ))}
      </Tabs>

      {languages.map((lang, idx) => {
        const result = uploadResults[lang];
        if (!result) return null;

        return (
          <TabPanel key={lang} value={validResultTab} index={idx} idPrefix="result">
            {result.status === "FAILURE" ? (
              <Box mt={2} p={3} border="1px solid #f5c6cb" borderRadius={2} bgcolor="#f8d7da">
                <Typography variant="h6" fontWeight="bold" color="error">
                  {t("upload-failed")}
                </Typography>
                <Typography variant="body1" color="error" mt={1}>
                  {result.error || t("task-failed-processing")}
                </Typography>
              </Box>
            ) : (
              <>
                {result.status === "PARTIAL" && (
                  <Box mt={2} mb={3} p={2} border="1px solid #ffeeba" borderRadius={2} bgcolor="#fff3cd">
                    <Typography variant="subtitle1" fontWeight="bold" sx={{ color: "warning.main" }}>
                      {t("partial-success")}
                    </Typography>
                    <Typography variant="body2" sx={{ color: "warning.main" }}>
                      {result.warnings || result.error || t("partial-warning-default")}
                    </Typography>
                  </Box>
                )}

                {result.data && (
                  <>
                    <img
                      src={result.data.file_link}
                      alt="Uploaded File"
                      style={{ maxWidth: "100%", height: "380px", width: "auto" }}
                    />
                    <Box display="flex" justifyContent="center" mt={2}>
                      <TextField
                        sx={{ width: "650px" }}
                        value={(() => {
                          const fileName = decodeURIComponent(result.data.wikipage_url).split("/").pop();
                          return fileName.includes(":") ? fileName.substring(fileName.indexOf(":") + 1) : fileName;
                        })()}
                        disabled={true}
                        slotProps={{
                          input: {
                            endAdornment: (
                              <InputAdornment position="end">
                                <Button
                                  variant="contained"
                                  color="primary"
                                  onClick={() => {
                                    const fileName = decodeURIComponent(result.data.wikipage_url).split("/").pop();
                                    const nameOnly = fileName.includes(":") ? fileName.substring(fileName.indexOf(":") + 1) : fileName;
                                    navigator.clipboard.writeText(nameOnly);
                                  }}
                                >
                                  {t("copy")}
                                </Button>
                              </InputAdornment>
                            ),
                          },
                        }}
                      />
                    </Box>
                    
                    <Stack
                      direction={{ xs: "column", sm: "row" }}
                      spacing={1.5}
                      justifyContent="center"
                      sx={{ mt: 3, mb: 2 }}
                    >
                      <Button
                        variant="contained"
                        color="primary"
                        href={result.data.wikipage_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {t("view-wiki-page")}
                      </Button>

                      <Button
                        variant="outlined"
                        onClick={() => navigate("/")}
                      >
                        {t("go-back-to-home")}
                      </Button>
                    </Stack>

                    {languageData[lang]?.editArticle && (
                      <Card
                        variant="outlined"
                        sx={{ mt: 4, mb: 3, textAlign: "left", borderRadius: 2 }}
                      >
                        <CardHeader
                          title={t("edit-article") || "Edit Article"}
                          subheader={
                            t("edit-article-description") ||
                            "Review and modify the target article wikitext before publishing."
                          }
                        />

                        <CardContent>
                          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                            {t("target-article") || "Target article"}
                          </Typography>

                          {(() => {
                            const articleName = languageData[lang].articleLink || "";
                            const finalHref = `https://${lang}.${project}.org/wiki/${encodeURIComponent(articleName)}`;
                            
                            let decodedName = articleName;
                            try {
                              decodedName = decodeURIComponent(articleName);
                            } catch (e) {}

                            return (
                              <Link
                                href={finalHref}
                                target="_blank"
                                rel="noopener noreferrer"
                                underline="hover"
                                sx={{ display: "block", mb: 3, wordBreak: "break-word" }}
                              >
                                {decodedName}
                              </Link>
                            );
                          })()}

                          {articleEditSuccess[lang] && (
                            <Alert severity="success" sx={{ mb: 3 }}>
                              {t("article-edit-success") || "Article updated successfully."}
                            </Alert>
                          )}

                          {result.data?.wikitext_fetch_success ? (
                            <>
                              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                {t("article-wikitext") || "Article wikitext"}
                              </Typography>

                              <TextField
                                multiline
                                minRows={12}
                                maxRows={30}
                                fullWidth
                                value={editableWikitexts[lang] || ""}
                                onChange={(e) => onEditableWikitextChange(lang, e.target.value)}
                                placeholder={t("article-wikitext-placeholder") || "Enter article wikitext..."}
                                helperText={t("article-wikitext-help") || "Changes will be submitted to the target article."}
                                disabled={editingState[lang]}
                                sx={{
                                  "& .MuiInputBase-root": {
                                    alignItems: "flex-start",
                                    fontFamily: "monospace",
                                    fontSize: "0.875rem",
                                    lineHeight: 1.6,
                                    bgcolor: "white",
                                  },
                                }}
                              />
                            </>
                          ) : (
                            <Alert severity="error">
                              {t("wikitext-fetch-failed") ||
                                "The article wikitext could not be fetched. You can manually edit the article using the link above."}
                            </Alert>
                          )}
                        </CardContent>

                        {result.data?.wikitext_fetch_success && (
                          <CardActions sx={{ justifyContent: "flex-end", px: 2, pb: 2 }}>
                            <Button
                              variant="contained"
                              color="primary"
                              onClick={() => onEditArticle(lang)}
                              disabled={editingState[lang]}
                            >
                              {editingState[lang] ? (
                                <>
                                  <CircularProgress size={18} color="inherit" sx={{ mr: 1 }} />
                                  {t("saving") || "Saving..."}
                                </>
                              ) : (
                                t("save-changes") || "Save Changes"
                              )}
                            </Button>
                          </CardActions>
                        )}
                      </Card>
                    )}
                  </>
                )}
              </>
            )}
          </TabPanel>
        );
      })}
    </>
  );
};

export default UploadResultsView;
