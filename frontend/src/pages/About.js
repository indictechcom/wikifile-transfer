import React from 'react';
import { Box, Typography, Button, Link, List, ListItem } from '@mui/material';
import { useTranslation } from "react-i18next";

function About() {
  const { t } = useTranslation();

  return (
    <Box sx={{ padding: 3 }}>
      <Typography variant="h4" gutterBottom>
        {t('about-the-tool')}
      </Typography>
      <Typography variant="body1">
        {t('tool-info2')}
      </Typography>
      
      <Button 
        style={{ marginTop: '1rem' }}
        variant="contained"
        color="primary" 
        component={Link}
        href="https://meta.wikimedia.org/wiki/Indic-TechCom/Tools/Wikifile-transfer" 
        target="_blank"
      >
        {t('learn-more')}
      </Button>

      <Box sx={{ marginTop: 4 }}>
        <Typography variant="h5" gutterBottom>
          {t('authors')}
        </Typography>
        <List sx={{ listStyleType: 'disc', pl: 2 }}>
          <ListItem sx={{ display: 'list-item' }}>
            <Link href="https://meta.wikimedia.org/wiki/User:Jayprakash12345" target="_blank" underline="hover" color="primary">
              Jay Pakash (Original v1)
            </Link>
          </ListItem>
          <ListItem sx={{ display: 'list-item' }}>
            <Link href="https://meta.wikimedia.org/wiki/User:ParasharSarthak" target="_blank" underline="hover" color="primary">
              Sarthak Parashar (Rewrite v2)
            </Link>
          </ListItem>
        </List>
      </Box>

      <Box sx={{ marginTop: 4 }}>
        <Typography variant="h5" gutterBottom>
          {t('tool-source')}
        </Typography>
        <Typography variant="span">
          {t('source-code-text')}: {""}
        </Typography>
        <Link href="https://github.com/indictechcom/wikifile-transfer" target="_blank" color="primary" underline="hover">
          {t('github')}
        </Link>
      </Box>
    </Box>
  );
}

export default About;
