import { visitHashRoute } from '../../support/utils';

describe('Internationalization', () => {
  beforeEach(() => {
    cy.stubAppBoot();
    cy.setAuthState(false);
  });

  it('switches app language and persists to backend API', () => {
    cy.intercept('POST', '**/api/user_language', { statusCode: 200 }).as('saveLang');
    visitHashRoute('/');

    cy.get('.MuiAppBar-root [role="combobox"]').click();
    cy.get('[role="listbox"] [role="option"]').contains('हिन्दी').click();

    cy.wait('@saveLang').its('request.body').should('deep.equal', {
      user_language: 'hi'
    });
  });

  it('updates visible text when language changes', () => {
    cy.intercept('POST', '**/api/user_language', { statusCode: 200 }).as('saveLang');
    visitHashRoute('/');

    // Verify initial English text
    cy.contains('Welcome').should('be.visible');

    cy.get('.MuiAppBar-root [role="combobox"]').click();
    cy.get('[role="listbox"] [role="option"]').contains('हिन्दी').click();

    cy.wait('@saveLang');

    // After switching, English text should no longer appear
    cy.contains('Welcome').should('not.exist');
  });
});