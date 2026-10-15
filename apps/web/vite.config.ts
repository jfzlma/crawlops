import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: "charts", test: /node_modules\/(?:recharts|recharts-scale|victory-vendor|d3-[^/]+)\//, priority: 20 },
            { name: "vendor", test: /node_modules\/(?:react|react-dom|react-router|react-router-dom|scheduler|@tanstack)\//, priority: 10 },
          ],
        },
      },
    },
  },
  server: { proxy: { "/api": "http://localhost:8000" } },
});
