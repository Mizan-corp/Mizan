import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { Root, makeQueryClient } from "./Root";
import "./fonts.css";
import "@/styles.css";

document.documentElement.classList.toggle(
  "dark",
  (localStorage.getItem("mizan.theme") ?? localStorage.getItem("vendora.theme") ?? "light") === "dark",
);

// This domain used to host the ERP as an offline-capable PWA. The website is
// not a PWA: drop any service worker left behind by the old app.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.getRegistrations().then((regs) => regs.forEach((r) => r.unregister())).catch(() => {});
}

const Router = ({ children }: { children: ReactNode }) => (
  <BrowserRouter basename={import.meta.env.BASE_URL}>{children}</BrowserRouter>
);

const container = document.getElementById("root")!;
const tree = <Root router={Router} queryClient={makeQueryClient()} />;

// Public pages arrive pre-rendered (ADR-016): React takes over the HTML that is already there.
// Application pages (signup, onboarding, the developer portal…) come as the empty shell.
if (container.dataset.prerendered) {
  ReactDOM.hydrateRoot(container, tree);
} else {
  ReactDOM.createRoot(container).render(tree);
}
