import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// manualChunks keeps the CodeMirror + Lezer family in its own long-lived chunk.
// The `pdf` and `grid` branches were removed with the unused `pdfjs-dist` and
// `ag-grid-*` dependencies: no such chunk was ever emitted, so they were dead.
export default defineConfig({ plugins: [react()], server: { proxy: { '/api': 'http://127.0.0.1:8000' } }, build: { target: 'es2022', rollupOptions: { output: { manualChunks(id) { if (id.includes('@codemirror') || id.includes('@lezer')) return 'codemirror'; } } } } });
