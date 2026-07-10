// ***********************************************
// Cypress Custom Commands for WikiFile-Transfer
// ***********************************************

/**
 * Stubs the /api/user endpoint to simulate a logged-in user.
 * Also intercepts /api/preference and /api/user_language with defaults.
 *
 * @param {string} username - The username to simulate
 */
Cypress.Commands.add('login', (username = 'TestUser') => {
  cy.intercept('GET', '**/api/user', {
    statusCode: 200,
    body: { logged: true, username },
  }).as('getUser');
});

/**
 * Stubs the /api/user endpoint to simulate a logged-out user.
 */
Cypress.Commands.add('logout', () => {
  cy.intercept('GET', '**/api/user', {
    statusCode: 200,
    body: { logged: false, username: null },
  }).as('getUser');
});

/**
 * Stubs the /api/preference GET endpoint with configurable overrides.
 *
 * @param {Object} overrides - Override default preference values
 * @param {string} [overrides.project='wikipedia'] - Preferred project
 * @param {string} [overrides.lang='en'] - Preferred language
 * @param {boolean} [overrides.skip_upload_selection=false] - Skip upload step
 */
Cypress.Commands.add('stubPreferences', (overrides = {}) => {
  const defaults = {
    project: 'wikipedia',
    lang: 'en',
    skip_upload_selection: false,
  };
  const data = { ...defaults, ...overrides };

  cy.intercept('GET', '**/api/preference', {
    statusCode: 200,
    body: { success: true, data, error: [] },
  }).as('getPreferences');
});

/**
 * Stubs the /api/user_language GET endpoint.
 *
 * @param {string} lang - The user's interface language code
 */
Cypress.Commands.add('stubUserLanguage', (lang = 'en') => {
  cy.intercept('GET', '**/api/user_language', {
    statusCode: 200,
    body: { success: true, data: { user_language: lang }, error: [] },
  }).as('getUserLanguage');
});

/**
 * Convenience command to stub all common API defaults for E2E tests.
 * Stubs user as logged out, preferences as defaults, and language as English.
 */
Cypress.Commands.add('stubAllApiDefaults', () => {
  cy.logout();
  cy.stubPreferences();
  cy.stubUserLanguage();
});

/**
 * Stubs the /api/upload POST endpoint.
 *
 * @param {Object} response - The response to return
 * @param {number} [statusCode=200] - HTTP status code
 */
Cypress.Commands.add('stubUpload', (response, statusCode = 200) => {
  cy.intercept('POST', '**/api/upload', {
    statusCode,
    body: response,
  }).as('uploadFile');
});

/**
 * Stubs the /api/task_status/:id GET endpoint for async upload polling.
 *
 * @param {string} taskId - The task ID to match
 * @param {Object} response - The response body
 */
Cypress.Commands.add('stubTaskStatus', (taskId, response) => {
  cy.intercept('GET', `**/api/task_status/${taskId}`, {
    statusCode: 200,
    body: response,
  }).as('getTaskStatus');
});

/**
 * Stubs the /api/get_wikitext GET endpoint.
 *
 * @param {string} wikitext - The wikitext content to return
 */
Cypress.Commands.add('stubWikitext', (wikitext = '== Description ==\nSample wikitext content') => {
  cy.intercept('GET', '**/api/get_wikitext**', {
    statusCode: 200,
    body: { wikitext },
  }).as('getWikitext');
});

/**
 * Stubs the /api/edit_page POST endpoint.
 *
 * @param {boolean} [success=true] - Whether the edit succeeds
 */
Cypress.Commands.add('stubEditPage', (success = true) => {
  cy.intercept('POST', '**/api/edit_page', {
    statusCode: success ? 200 : 500,
    body: {
      success,
      data: {},
      errors: success ? [] : ['Edit Error'],
    },
  }).as('editPage');
});

/**
 * Stubs the /api/preference POST endpoint for saving preferences.
 */
Cypress.Commands.add('stubSavePreferences', () => {
  cy.intercept('POST', '**/api/preference', {
    statusCode: 200,
    body: { success: true, data: {}, errors: [] },
  }).as('savePreferences');
});

/**
 * Stubs the /api/user_language POST endpoint for saving language preferences.
 */
Cypress.Commands.add('stubSaveUserLanguage', () => {
  cy.intercept('POST', '**/api/user_language', {
    statusCode: 200,
    body: { success: true, data: {}, errors: [] },
  }).as('saveUserLanguage');
});

/**
 * Stubs the Wikimedia API call used to validate target file name existence.
 * Simulates a file that does NOT exist (page id = -1 with 'missing' key).
 */
Cypress.Commands.add('stubWikimediaFileCheck', () => {
  cy.intercept('GET', 'https://*.wikipedia.org/w/api.php?action=query*', {
    statusCode: 200,
    body: {
      query: {
        pages: {
          '-1': {
            ns: 6,
            title: 'File:TestFile.jpg',
            missing: '',
          },
        },
      },
    },
  }).as('wikimediaFileCheck');
});
