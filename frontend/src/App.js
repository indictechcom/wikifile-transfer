import { createHashRouter, Outlet, RouterProvider } from "react-router-dom";
import { Container } from "@mui/material";
import { useDispatch } from "react-redux";
import { useEffect } from "react";
import { fetchUser } from "./redux/userAuth/authSlice";
import { I18nextProvider } from "react-i18next";
import { ToastContainer } from "react-toastify";
import i18n from "./i18n";

import AppHeader from "./components/AppHeader";
import AppFooter from "./components/AppFooter";

// Import pages components
import Home from "./pages/Home";
import NotFound from "./pages/NotFound";
import Upload from "./pages/Upload";
import Preferences from "./pages/Preferences";
import About from "./pages/About";

const MainLayout = () => (
  <>
    <AppHeader />
    <Container style={{ paddingTop: 36, minHeight: "calc(100vh - 128px)" }}>
      <Outlet />
    </Container>
    <ToastContainer />
    <AppFooter />
  </>
);

const router = createHashRouter([
  {
    path: "/",
    element: <MainLayout />,
    children: [
      { path: "", element: <Home /> },
      { path: "upload", element: <Upload /> },
      { path: "preferences", element: <Preferences /> },
      { path: "about", element: <About /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

function App() {
  const dispatch = useDispatch();

  useEffect(() => {
    dispatch(fetchUser());
  }, [dispatch]);

  return (
    <I18nextProvider i18n={i18n}>
      <RouterProvider router={router} />
    </I18nextProvider>
  );
}

export default App;
