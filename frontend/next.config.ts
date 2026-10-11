import type { NextConfig } from "next";
import path from "node:path";
const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "host.docker.internal"],
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    root: path.resolve(__dirname, ".."),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
