import React from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App.jsx";
import "./styles.css";

// HashRouter keeps client routes (#/history ...) from colliding with the API paths (/runs ...).
createRoot(document.getElementById("root")).render(
  <HashRouter>
    <App />
  </HashRouter>
);
