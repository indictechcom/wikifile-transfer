import ISO6391 from 'iso-639-1';
import React, { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { nameInitials } from "../utils/helper";

import MenuIcon from "@mui/icons-material/Menu";
import AppBar from "@mui/material/AppBar";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import { useTheme } from "@mui/material/styles";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import useMediaQuery from "@mui/material/useMediaQuery";
import backendApi from "../utils/api";

import { resetUser } from "../redux/userAuth/authSlice";

const Header = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { logged: isLoggedIn, username } = useSelector((state) => state.auth);
  const { t, i18n } = useTranslation();
  const [value, setValue] = React.useState(0);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

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

  const handleDrawerNavigate = (path) => {
    navigate(path);
    setDrawerOpen(false);
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

  const languageSelector = (
    <Select
      value = {i18n.language}
      onChange={handleLanguageChange}
      variant="outlined"
      sx={{
        backgroundColor: "white",
        color: "black",
        minWidth: "120px",
        "& .MuiOutlinedInput-notchedOutline": { borderColor: "white" },
        "& .MuiSelect-select": { padding: "8px 20px" },
        "& .MuiSelect-icon": { color: "black" },
        "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: "lightgray" },
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
  );

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            <Link to="/" style={{ textDecoration: "none", color: "white" }}>
              {t("site-title")}
            </Link>
          </Typography>

          {!isMobile && (
            <>
              <Tabs value={value} onChange={handleChange} textColor="inherit">
                <Tab label={t('home')} />
                {isLoggedIn && <Tab label={t('upload')} />}
                {isLoggedIn && <Tab label={t('preference')} />}
                <Tab label={t('about')}  />
              </Tabs>
              {isLoggedIn ? (
                <>
                  <Avatar style={{ marginLeft: 12, marginRight: 12 }}>
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
              <Box sx={{ marginLeft: 2 }}>
                {languageSelector}
              </Box>
            </>
          )}

          {isMobile && (
            <IconButton
              color="inherit"
              onClick={() => setDrawerOpen(true)}
              aria-label = "open navigation menu"
            >
              <MenuIcon />
            </IconButton>
          )}
        </Toolbar>
      </AppBar>
      <Drawer anchor="right" open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <Box sx={{ width:260, padding:2 }}>
          <List>
            <ListItem disablePadding>
              <ListItemButton onClick = {() => handleDrawerNavigate("/")}>
                <ListItemText primary={t('home')} />
              </ListItemButton>
            </ListItem>
            {isLoggedIn && (
              <ListItem disablePadding>
                <ListItemButton onClick = {() => handleDrawerNavigate("/upload")}>
                  <ListItemText primary={t('upload')} />
                </ListItemButton>
              </ListItem>
            )}
            {isLoggedIn && (
              <ListItem disablePadding>
                <ListItemButton onClick = {() => handleDrawerNavigate("/preferences")}>
                  <ListItemText primary={t('preference')} />
                </ListItemButton>
              </ListItem>
            )}
            <ListItem disablePadding>
              <ListItemButton onClick = {() => handleDrawerNavigate("/about")}>
                <ListItemText primary={t('about')} />
              </ListItemButton>
            </ListItem>
          </List>
          <Divider />
          <Box sx = {{ padding: "16px 0" }}>
            {languageSelector}
          </Box>
          <Divider />
          <Box sx = {{ padding: "16px 0"}}>
            {isLoggedIn ? (
              <Box sx = {{ display: "flex", alignItems: "center", gap: 1}}>
                <Avatar>
                  {nameInitials(username)}
                </Avatar>
                <Button color="error" variant="outlined" onClick={handleLogout} fullWidth>
                  {t('logout')}
                </Button>
              </Box>
            ) : (
              <Button color="primary" variant="contained" onClick={handleLogin} fullWidth>
                {t('login')}
              </Button>
            )}
          </Box>
        </Box>
      </Drawer>
    </Box>
  );
};

export default Header;
