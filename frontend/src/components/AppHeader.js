import React, { useEffect } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useSelector, useDispatch } from "react-redux";
import { useTranslation } from "react-i18next";
import ISO6391 from 'iso-639-1';
import { nameInitials } from "../utils/helper";

import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import Avatar from "@mui/material/Avatar";
import Button from "@mui/material/Button";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import backendApi from "../utils/api";

import { resetUser } from "../redux/userAuth/authSlice";

const Header = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { logged: isLoggedIn, username } = useSelector((state) => state.auth);
  const { t, i18n } = useTranslation();
  const [value, setValue] = React.useState(0);

  const handleChange = (event, newValue) => {
    setValue(newValue);
    if (newValue === 0) navigate("/");
    else if (isLoggedIn && newValue === 1) navigate("/upload");
    else if (isLoggedIn && newValue === 2) navigate("/preferences");
    else if (newValue === (isLoggedIn ? 3 : 1)) navigate("/about");
  };

  const handleLogout = () => {
    dispatch(resetUser());
    window.location.href = backendApi.defaults.baseURL + "/logout";
  };

  const handleLogin = () => {
    window.location.href = backendApi.defaults.baseURL + "/login";
  };

  const location = useLocation();

  useEffect(() => {
    if (location.pathname === "/") setValue(0);
    else if (location.pathname === "/upload") setValue(1);
    else if (location.pathname === "/preferences") setValue(2);
    else if (location.pathname === "/about") setValue(isLoggedIn ? 3 : 1);
  }, [location, isLoggedIn]);

  const handleLanguageChange = (event) => {
    const payload = {
      user_language: event.target.value,
    };

    backendApi.post("/api/user_language", payload);

    i18n.changeLanguage(event.target.value);
  };

  useEffect(() => {
    backendApi.get("/api/user_language").then((resp) => {
      i18n.changeLanguage(resp.data.data.user_language);
    });
  }, [i18n]);

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            <Link to="/" style={{ textDecoration: "none", color: "white" }}>
              {t("site-title")}
            </Link>
          </Typography>
          <Tabs value={value} onChange={handleChange} textColor="inherit">
            <Tab label={t('home')} />
            {isLoggedIn && <Tab label={t('upload')} />}
            {isLoggedIn && <Tab label={t('preference')} />}
            <Tab label={t('about')}  />
          </Tabs>
          {isLoggedIn ? (
            <>
              <Avatar style={{ marginRight: 12 }}>
                {nameInitials(username)}
              </Avatar>
              <Button color="inherit" variant="outlined" onClick={handleLogout}>
              {t('logout')}
              </Button>
            </>
          ) : (
            <Button color="inherit" variant="outlined" onClick={handleLogin}>
              {t('login')}
            </Button>
          )}
          <Select
            value={i18n.language}
            onChange={handleLanguageChange}
            variant="outlined"
            sx={{
              marginLeft: 2,
              backgroundColor: "white",
              color: "black",
              minWidth: "120px",
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: "white",
              },
              "& .MuiSelect-select": {
                padding: "8px 20px",
              },
              "& .MuiSelect-icon": { color: "black" },
              "&:hover .MuiOutlinedInput-notchedOutline": {
                borderColor: "lightgray",
              },
            }}
          >
            {i18n.options.supportedLngs
              .filter((lng) => lng !== "cimode")
              .map((lng) => (
                <MenuItem key={lng} value={lng}>
                  {ISO6391.getNativeName(lng) || lng}
                </MenuItem>
              ))}
          </Select>
        </Toolbar>
      </AppBar>
    </Box>
  );
};

export default Header;
