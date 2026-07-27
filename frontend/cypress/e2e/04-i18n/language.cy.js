import { visitHashRoute } from '../../support/utils';

describe('Internationalization', () => {
  it('switches app language and persists to backend API', () => {
    cy.intercept('POST', '**/api/user_language', { statusCode: 200 }).as('saveLang');
    visitHashRoute('/');

    cy.get('.MuiAppBar-root .MuiSelect-select').click();
    cy.get('[role="listbox"] [role="option"]').contains('हिन्दी').click();

    cy.wait('@saveLang').its('request.body').should('deep.equal', {
      user_language: 'hi'
    });
  });
});