import { Typography, Button } from "@mui/material";
import { useNavigate } from 'react-router-dom';
import { useSelector } from "react-redux";
import backendApi from '../utils/api';

import { useTranslation } from 'react-i18next';

function Home() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const { logged: isLoggedIn } = useSelector((state) => state.auth);

  const handleStartUpload = () => {
    navigate("/upload");
  }
  const handleLogin = () => {
    window.location.href = backendApi.defaults.baseURL + '/login';
  };

  return (
    <>
      <Typography>
      { t('tool-info1') }
      </Typography>
      {isLoggedIn ? (
        <Button style={{ marginTop: 48 }} variant="contained" color="success" onClick={handleStartUpload}>
          { t('start-uploading') }
        </Button>
      ) : (
        <Button style={{ marginTop: 48 }} variant="outlined" onClick={handleLogin}>
          { t('login-to-upload-images') }
        </Button>
      )}
    </>
  );
}

export default Home;
