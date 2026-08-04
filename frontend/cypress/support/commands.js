/**
 * @see ../../../custom-commands.d.ts for TypeScript definitions.
 */

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
  cy.intercept('POST', '**/api/upload_multi', { statusCode, fixture: fixturePath }).as('uploadFile');
});

Cypress.Commands.add('stubWikimediaFileCheck', (exists = false) => {
  cy.intercept('GET', '**/w/api.php?action=query*', {
    statusCode: 200,
    body: { query: { pages: { '-1': { ns: 6, title: 'File:TestFile.jpg', ...(exists ? {} : { missing: '' }) } } } }
  }).as('wikimediaFileCheck');
});