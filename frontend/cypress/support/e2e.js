// ***********************************************
// E2E Support File for WikiFile-Transfer
//
// Loaded automatically before every E2E spec.
// ***********************************************

import './commands';

// Stub the most common API calls before every test so
// the app can boot without hitting the real backend.
beforeEach(() => {
  cy.stubAllApiDefaults();
});
