/** @type {import('next').NextConfig} */
const nextConfig={
  output:'standalone',
  serverExternalPackages:['pdf-parse','mammoth'],
};
export default nextConfig;
