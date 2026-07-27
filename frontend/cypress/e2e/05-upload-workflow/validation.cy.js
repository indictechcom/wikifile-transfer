import { visitHashRoute } from '../../support/utils';

describe('Upload Workflow: Validations & Errors', () => {
  beforeEach(() => {
    cy.setAuthState(true);
    visitHashRoute('/upload');
  });

  it('prevents proceeding if URL is empty', () => {
    cy.contains('button', /next/i).click();
    cy.contains('Please enter a valid source URL').should('be.visible');
  });

  it('handles server 500 errors gracefully', () => {
    cy.intercept('POST', '**/api/upload', {
      statusCode: 500,
      body: { errors: ['An error occurred during upload'] }
    }).as('uploadError');
    
    cy.get('input[type="text"]').first().type('https://en.wikipedia.org/wiki/File:Bad.jpg');
    cy.contains('button', /next/i).click();
    cy.contains('button', /next/i).click();
    
    cy.contains('button', /Upload file/i).click();
    cy.wait('@uploadError');
    cy.contains('An error occurred during upload').should('be.visible');
  });
});