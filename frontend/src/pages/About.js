import React, { useState } from 'react';
import {
  Box,
  TextField,
  Select,
  MenuItem,
  Button,
  Stepper,
  Step,
  StepLabel,
  Typography,
  FormControl,
  InputLabel,
  Checkbox,
  FormControlLabel,
} from '@mui/material';

function Upload() {
  const [activeStep, setActiveStep] = useState(0);
  const [sourceUrl, setSourceUrl] = useState('');
  const [project, setProject] = useState('');
  const [language, setLanguage] = useState('');
  const [targetFileName, setTargetFileName] = useState('');
  const [file, setFile] = useState(null);
  const [addTemplate, setAddTemplate] = useState(false);
  const [templateContent, setTemplateContent] = useState('');

  const steps = [
    'Enter Source URL',
    'Select Project and Language',
    'Upload File & Name',
    'Add Template (Optional)',
  ];

  const handleNext = () => {
    if (isStepValid()) {
      setActiveStep((prevStep) => prevStep + 1);
    } else {
      alert("Please complete all required fields.");
    }
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleUpload = () => {
    console.log('Uploading to Target wiki with the following details:', {
      sourceUrl,
      project,
      language,
      targetFileName,
      file,
      addTemplate,
      templateContent,
    });
  };

  const isStepValid = () => {
    switch (activeStep) {
      case 0:
        return sourceUrl.trim() !== '';
      case 1:
        return project !== '' && language !== '';
      case 2:
        return targetFileName.trim() !== '' && file !== null;
      default:
        return true;
    }
  };

  return (
    <Box sx={{ maxWidth: 650, margin: 'auto', padding: 3 }}>
      <Stepper activeStep={activeStep} alternativeLabel>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {activeStep === steps.length ? (
        <Box textAlign="center">
          <Typography variant="h6" gutterBottom>
            All steps completed - ready to upload!
          </Typography>
          <Button variant="contained" color="primary" onClick={handleUpload}>
            Upload to Target wiki
          </Button>
        </Box>
      ) : (
        <Box>
          {activeStep === 0 && (
            <TextField
              label="Enter Source URL"
              placeholder="Ex. https://en.wikipedia.org/wiki/File:ABCD.jpg"
              fullWidth
              margin="normal"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              required
            />
          )}

          {activeStep === 1 && (
            <>
              <FormControl fullWidth margin="normal" required>
                <InputLabel>Select Project</InputLabel>
                <Select
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                >
                  <MenuItem value="Wikiversity">Wikiversity</MenuItem>
                  <MenuItem value="Wikipedia">Wikipedia</MenuItem>
                  <MenuItem value="Wiktionary">Wiktionary</MenuItem>
                </Select>
              </FormControl>
              <FormControl fullWidth margin="normal" required>
                <InputLabel>Select Language</InputLabel>
                <Select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <MenuItem value="Hindi">Hindi</MenuItem>
                  <MenuItem value="English">English</MenuItem>
                  <MenuItem value="Spanish">Spanish</MenuItem>
                </Select>
              </FormControl>
            </>
          )}

          {activeStep === 2 && (
            <>
              <TextField
                label="Name of the Target file"
                placeholder="Ex. ABCD"
                fullWidth
                margin="normal"
                value={targetFileName}
                onChange={(e) => setTargetFileName(e.target.value)}
                required
              />
              <Button
                variant="outlined"
                component="label"
                fullWidth
                sx={{ mt: 2 }}
              >
                Upload File
                <input
                  type="file"
                  hidden
                  onChange={(e) => setFile(e.target.files[0])}
                />
              </Button>
              {file && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Selected file: {file.name}
                </Typography>
              )}
            </>
          )}

          {activeStep === 3 && (
            <>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={addTemplate}
                    onChange={(e) => setAddTemplate(e.target.checked)}
                  />
                }
                label="Add Template"
              />
              {addTemplate && (
                <TextField
                  label="Template Content"
                  placeholder="Enter template details here"
                  multiline
                  rows={4}
                  fullWidth
                  margin="normal"
                  value={templateContent}
                  onChange={(e) => setTemplateContent(e.target.value)}
                />
              )}
            </>
          )}

          <Box display="flex" justifyContent="space-between" mt={2}>
            <Button disabled={activeStep === 0} onClick={handleBack}>
              Back
            </Button>
            <Button
              variant="contained"
              color="primary"
              onClick={activeStep === steps.length - 1 ? handleUpload : handleNext}
            >
              {activeStep === steps.length - 1 ? 'Finish' : 'Next'}
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
}

export default Upload;