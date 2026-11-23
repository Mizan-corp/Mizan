import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {fileURLToPath} from 'node:url';
// Static native editor only. No configureServer, spawned Python, proxy token or
// embedded credentials. The hosting environment owns its isolated /api service.
export default defineConfig({plugins:[react()],build:{sourcemap:false,rollupOptions:{input:fileURLToPath(new URL('./studio-preview.html',import.meta.url))}}});
