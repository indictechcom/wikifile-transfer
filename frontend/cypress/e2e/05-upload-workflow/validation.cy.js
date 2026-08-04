// Tests validation rules and error handling across the 5-step multi-language
// upload workflow introduced in the updated Upload.js.

import { visitHashRoute } from '../../support/utils';

describe('Upload Workflow: Validations & Errors', () => {
  beforeEach(() => {
    cy.stubAppBoot();
    cy.setAuthState(true);
  });

  it('prevents proceeding when source URL is empty → shows toast error', () => {
    visitHashRoute('/upload');

    // Step 0: attempt to advance without entering any URL
    cy.contains('button', /next/i).click();
    cy.contains('Please enter a valid source URL').should('be.visible');
  });

  it('prevents proceeding when URL lacks /wiki/ path → shows toast error', () => {
    visitHashRoute('/upload');

    // Step 0: enter a URL missing the required /wiki/ segment
    cy.get('input[type="text"]').first().type('https://en.wikipedia.org/invalid/File:Test.jpg');
    cy.contains('button', /next/i).click();
    cy.contains('Please enter a valid source URL').should('be.visible');
  });

  it('prevents proceeding when project and language are not selected → shows toast error', () => {
    // Override preferences with empty project and language so step 1 has nothing pre-selected
    cy.intercept('GET', '**/api/preference', {
      statusCode: 200,
      body: { success: true, data: { project: '', lang: '', skip_upload_selection: false }, error: [] }
    }).as('getPrefsEmpty');
    visitHashRoute('/upload');

    // Step 0: enter a valid URL and advance
    cy.get('input[type="text"]').first().type('https://en.wikipedia.org/wiki/File:Test.jpg');
    cy.contains('button', /next/i).click();

    // Step 1: project and language are empty — attempting to proceed should fail
    cy.contains('button', /next/i).click();
    cy.contains('Please select a valid project and language').should('be.visible');
  });

  it('shows back button only on steps 1 and 2 → hidden on steps 0, 3, and 4', () => {
    cy.stubWikimediaFileCheck(false);
    cy.intercept('GET', '**/api/get_wikitext**', { fixture: 'upload/wikitext-template.json' }).as('getWikiText');
    visitHashRoute('/upload');

    // Step 0: no Back button should be rendered
    cy.contains('button', /back/i).should('not.exist');

    // Advance to Step 1
    cy.get('input[type="text"]').first().type('https://en.wikipedia.org/wiki/File:Test.jpg');
    cy.contains('button', /next/i).click();

    // Step 1: Back button should be visible
    cy.contains('label', /select project/i).should('be.visible');
    cy.contains('button', /back/i).should('be.visible');
    cy.contains('button', /next/i).click();

    // Step 2: Back button should be visible
    cy.contains('label', /Name of the Target file/i).should('be.visible');
    cy.contains('button', /back/i).should('be.visible');
    cy.contains('button', /next/i).click();
    cy.wait('@wikimediaFileCheck');

    // Step 3: Back button should NOT be rendered
    cy.get('textarea').should('be.visible');
    cy.contains('button', /back/i).should('not.exist');
    cy.contains('button', /next/i).click();

    // Step 4: Back button should NOT be rendered
    cy.contains('button', /upload file to target wiki/i).should('be.visible');
    cy.contains('button', /back/i).should('not.exist');
  });

  it('handles server 500 error on upload → shows error toast', () => {
    cy.intercept('POST', '**/api/upload_multi', {
      statusCode: 500,
      body: { errors: ['Internal server error'] }
    }).as('uploadError');
    cy.stubWikimediaFileCheck(false);
    cy.intercept('GET', '**/api/get_wikitext**', { fixture: 'upload/wikitext-template.json' }).as('getWikiText');
    visitHashRoute('/upload');

    // Step 0: enter URL
    cy.get('input[type="text"]').first().type('https://en.wikipedia.org/wiki/File:Bad.jpg');
    cy.contains('button', /next/i).click();

    // Step 1: defaults pre-populated via preferences (wikipedia, en)
    cy.contains('label', /select project/i).should('be.visible');
    cy.contains('button', /next/i).click();

    // Step 2: target file name auto-populated from URL
    cy.contains('label', /Name of the Target file/i).should('be.visible');
    cy.contains('button', /next/i).click();
    cy.wait('@wikimediaFileCheck');

    // Step 3: template — advance past it
    cy.get('textarea').should('be.visible');
    cy.contains('button', /next/i).click();

    // Step 4: click upload — should trigger the 500 error
    cy.contains('button', /upload file to target wiki/i).click();
    cy.wait('@uploadError');

    // Error toast should be displayed
    cy.contains('An error occurred during upload').should('be.visible');
  });
});