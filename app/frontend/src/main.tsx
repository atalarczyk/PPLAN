import React from "react";
import ReactDOM from "react-dom/client";

import { AppRouter } from "./app/router";
import { AuthProvider } from "./app/auth/AuthProvider";
import { initializeMicrosoftAuthBridge } from "./app/auth/microsoft";
import "./styles.css";

initializeMicrosoftAuthBridge();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  </React.StrictMode>,
);

