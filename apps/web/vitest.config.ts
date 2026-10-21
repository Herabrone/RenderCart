import { defineConfig } from "vitest/config";
import path from "node:path";

const vitestConfig = defineConfig({
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  test: { environment: "node" },
});

export default vitestConfig;
