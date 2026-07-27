const { defineConfig } = require('cypress');

module.exports = defineConfig({
  projectId: 'wikifile-transfer',
  viewportWidth: 1280,
  viewportHeight: 720,
  retries: {
    runMode: 2, // Retry failed tests in CI (GitHub Actions/Toolforge)
    openMode: 0, // No retries during local development
  },
  e2e: {
    baseUrl: 'http://localhost:3000',
    specPattern: 'cypress/e2e/**/*.cy.js',
    supportFile: 'cypress/support/e2e.js',
    experimentalRunAllSpecs: true,
    defaultCommandTimeout: 8000, 
    requestTimeout: 10000,
  },
});