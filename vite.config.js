import { resolve } from 'path';

export default {
    base: './',
    optimizeDeps: { exclude: ["fsevents"] },
    publicDir: 'public',
    build: {
        rollupOptions: {
            input: {
                main: resolve(import.meta.dirname, 'index.html'),
                help: resolve(import.meta.dirname, 'help.html')
            }
        }
    }
}