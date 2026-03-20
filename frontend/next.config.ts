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
  async redirects() {
    return [
      {
        source: '/insights',
        destination: '/blog',
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
