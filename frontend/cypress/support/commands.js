// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add('login', (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })

Cypress.Commands.add('setAuthState', (isLoggedIn = true, username = 'TestUser') => {
  // Use inline body so we can dynamically inject any username (fixes the 'W' vs 'T' avatar issue)
  cy.intercept('GET', '**/api/user', {
    statusCode: 200,
    body: { logged: isLoggedIn, username: isLoggedIn ? username : null }
  }).as('getUser');
});

Cypress.Commands.add('stubAppBoot', () => {
  cy.intercept('GET', '**/api/preference', { fixture: 'user/preferences-default.json' }).as('getPrefs');
  cy.intercept('GET', '**/api/user_language', { fixture: 'user/language-en.json' }).as('getLang');
  cy.setAuthState(false); // Default to logged out
});

Cypress.Commands.add('stubTaskStatus', (taskId, fixturePath) => {
  cy.intercept('GET', `**/api/task_status/${taskId}`, { fixture: fixturePath }).as('getTaskStatus');
});

Cypress.Commands.add('stubUpload', (fixturePath, statusCode = 200) => {
  cy.intercept('POST', '**/api/upload', { statusCode, fixture: fixturePath }).as('uploadFile');
});

Cypress.Commands.add('stubWikimediaFileCheck', (exists = false) => {
  cy.intercept('GET', 'https://*.wikipedia.org/w/api.php?action=query*', {
    statusCode: 200,
    body: { query: { pages: { '-1': { ns: 6, title: 'File:TestFile.jpg', ...(exists ? {} : { missing: '' }) } } } }
  }).as('wikimediaFileCheck');
});