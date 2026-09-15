import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], server: { proxy: { '/api': 'http://127.0.0.1:8000' } }, build: { target: 'es2022', rollupOptions: { output: { manualChunks(id) { if (id.includes('@codemirror')) return 'codemirror'; if (id.includes('pdfjs-dist')) return 'pdf'; if (id.includes('ag-grid')) return 'grid'; } } } } });
