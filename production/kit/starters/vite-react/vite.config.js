import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// base: './' keeps every URL relative, so the build also works under a GitHub Pages subpath.
export default defineConfig({ plugins: [react()], base: './' });
