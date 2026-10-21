import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Local Windows previews can avoid standalone packaging's symlink privilege.
  // Docker and CI keep the default deployable standalone output.
  output:
    process.env.RENDERCART_LOCAL_PREVIEW === "1" ? undefined : "standalone",
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
};

export default nextConfig;
