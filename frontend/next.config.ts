import type { NextConfig } from "next";
import applicationConfig from "../config/application.json";

const backendInternalUrl = (process.env.BACKEND_INTERNAL_URL ?? applicationConfig.backend.internalUrl).replace(/\/$/, "");

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendInternalUrl}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
