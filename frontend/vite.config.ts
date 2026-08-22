import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

/**
 * MapLibre GL v6 loads its tiling web worker at runtime via
 *   new Worker(new URL('./maplibre-gl-worker.mjs', import.meta.url), { type: 'module' })
 * The current bundler (rolldown-vite) does not emit that worker chunk, so the file is
 * missing from dist/assets and the SPA fallback serves index.html for it — the worker
 * never starts and geojson layers never render. This plugin copies MapLibre's prebuilt
 * ES worker (+ its shared chunk) into the output assets dir so the URL resolves.
 */
function copyMaplibreWorker() {
  const files = ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']
  const src = resolve(__dirname, 'node_modules/maplibre-gl/dist')
  return {
    name: 'copy-maplibre-worker',
    apply: 'build' as const,
    writeBundle(options: { dir?: string }) {
      const outDir = options.dir || resolve(__dirname, 'dist')
      const assets = resolve(outDir, 'assets')
      if (!existsSync(assets)) mkdirSync(assets, { recursive: true })
      for (const f of files) {
        const from = resolve(src, f)
        if (existsSync(from)) copyFileSync(from, resolve(assets, f))
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), copyMaplibreWorker()],
  worker: { format: 'es' },
})
