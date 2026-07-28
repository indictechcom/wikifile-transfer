import { visitHashRoute } from '../../support/utils';

describe('Upload Workflow: Validations & Errors', () => {
  beforeEach(() => {
    cy.stubAppBoot();
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

    // Verify we advanced to step 2 before clicking Next again
    cy.contains(/select project/i).should('be.visible');
    cy.contains('button', /next/i).click();
    
    // Verify we advanced to step 3
    cy.contains(/name of the target file/i).should('be.visible');
    cy.contains('button', /Upload file/i).click();
    cy.wait('@uploadError');
    cy.contains('An error occurred during upload').should('be.visible');
  });
});