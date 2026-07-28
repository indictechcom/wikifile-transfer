// Global configuration and behavior that modifies Cypress.
// Read more here: https://on.cypress.io/configuration

// Import commands.js using ES2015 syntax:
import './commands';

Cypress.on('uncaught:exception', (err) => {
  console.error('App Error:', err);
  return false;
});

// Hide fetch/XHR requests from the Cypress UI log to reduce noise
const app = window.top;
if (!app.document.head.querySelector('[data-hide-command-log-request]')) {
  const style = app.document.createElement('style');
  style.innerHTML = '.command-name-request, .command-name-xhr { display: none; }';
  style.setAttribute('data-hide-command-log-request', '');
  app.document.head.appendChild(style);
}