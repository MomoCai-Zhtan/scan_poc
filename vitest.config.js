import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'happy-dom',
    include: ['scan_entry/tests/**/*.test.js'],
  },
});
