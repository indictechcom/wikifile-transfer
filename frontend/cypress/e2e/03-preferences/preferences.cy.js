import { visitHashRoute, selectMuiDropdown } from '../../support/utils';

describe('Preferences Form', () => {
  beforeEach(() => {
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
});