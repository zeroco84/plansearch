import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/webhooks/:path*',
        destination: 'http://coolify:8080/webhooks/:path*',
      },
    ];
  },
};

export default nextConfig;
