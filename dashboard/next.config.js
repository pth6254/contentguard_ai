/** @type {import('next').NextConfig} */
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*",   destination: `${API}/api/:path*` },
      { source: "/admin/:path*", destination: `${API}/admin/:path*` },
      { source: "/auth/:path*",  destination: `${API}/auth/:path*` },
      { source: "/register",     destination: `${API}/register` },
      { source: "/health",       destination: `${API}/health` },
    ]
  },
}
module.exports = nextConfig
