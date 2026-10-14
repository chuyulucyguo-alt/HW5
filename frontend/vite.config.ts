import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// `npm run dev` serves the desk on http://localhost:5173.
// The page calls the FastAPI backend directly at VITE_API_BASE (see .env, default http://localhost:8000);
// the backend's CORS settings allow this origin.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
})
