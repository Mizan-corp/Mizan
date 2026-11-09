import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import NotRunning from "./NotRunning";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>{location.hash === "#/not-running" ? <NotRunning /> : <App />}</React.StrictMode>,
);
