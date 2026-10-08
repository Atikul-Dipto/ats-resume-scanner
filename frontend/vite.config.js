import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/ats-resume-scanner/",
  server: {
    fs: {
      // The resume templates live in the backend (builder/templates.json) so
      // the preview and the exported files share one definition.
      allow: [".", "../backend/app/builder"],
    },
  },
});
