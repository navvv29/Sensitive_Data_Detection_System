import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // @ts-ignore - Next.js internal type mismatch for devIndicators
  devIndicators: {
    appIsrStatus: false,
    buildActivity: false,
  },
};

export default nextConfig;
