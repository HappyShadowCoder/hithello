import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// NOTE: @arcgis/vite-plugin is optional — it only copies ArcGIS worker/asset
// files into the production build output. For local development it is not
// required because Vite resolves @arcgis/core's ESM modules directly.
//
// To add it for production builds, run:
//   npm install -D @arcgis/vite-plugin
// Then uncomment the two lines below and re-add arcgis() to plugins[].
// import arcgis from '@arcgis/vite-plugin'

export default defineConfig({
  plugins: [
    // arcgis(),   ← uncomment after installing @arcgis/vite-plugin
    svelte(),
  ],
})
