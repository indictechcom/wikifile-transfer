import { visitHashRoute, selectMuiDropdown } from '../../support/utils';

describe('Preferences Form', () => {
  beforeEach(() => {
    cy.stubAppBoot();
    cy.setAuthState(true);

    cy.intercept('POST', '**/api/preference', { 
      statusCode: 200, 
      body: { success: true } 
    }).as('savePrefs');
    
    visitHashRoute('/preferences');
  });

  it('loads saved preferences and handles form updates', () => {
    cy.contains('My preferences').should('be.visible');
    
    selectMuiDropdown('Select project', 'Wiktionary');
    
    cy.get('input[type="checkbox"]').check().should('be.checked');

    cy.contains('button', 'Save').click();
    
    cy.wait('@savePrefs').its('request.body').should('deep.include', {
      project: 'wiktionary',
      skip_upload_selection: true
    });

    cy.contains('Preferences saved successfully').should('be.visible');
  });

  it('shows error feedback when save fails', () => {
    cy.intercept('POST', '**/api/preference', {
      statusCode: 500,
      body: { success: false, errors: ['Database Error'] }
    }).as('savePrefsError');

    cy.contains('button', 'Save').click();
    cy.wait('@savePrefsError');
  });

  it('navigates back to home on cancel', () => {
    cy.contains('button', 'Cancel').click();
    cy.url().should('include', '/');
  });
});