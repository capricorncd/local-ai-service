import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import remCss from './scripts/rem-css.mjs';
export default defineConfig({plugins:[react()],css:{postcss:{plugins:[remCss()]}},build:{rollupOptions:{input:{desktop:'index.html',mobile:'mobile.html'}}},server:{port:1422,strictPort:true},clearScreen:false});
