import React from "react";
import ReactDOM from "react-dom/client";
// HashRouter: the frontend is static files on GitHub Pages, which can't
// rewrite /ats-resume-scanner/builder to index.html on a hard refresh.
import { HashRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./auth/AuthContext.jsx";
import "./index.css";
import "./builder.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HashRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </HashRouter>
  </React.StrictMode>
);
