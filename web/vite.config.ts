import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built inside the image and served by FastAPI from the same origin, so there
// is no dev proxy and no CORS configuration to keep in sync.
export default defineConfig({ plugins: [react()] });
