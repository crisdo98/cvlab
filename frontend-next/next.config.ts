import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // The app is local-only and is served as static files by the existing
  // container alongside the FastAPI backend. No Node server is introduced.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // Without this Turbopack walks up past the repo looking for a lockfile.
  turbopack: { root: path.resolve(__dirname) },
};

export default nextConfig;
