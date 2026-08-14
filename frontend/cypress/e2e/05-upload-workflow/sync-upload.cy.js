// Tests the synchronous (HTTP 200) upload path across the 5-step
// multi-language workflow: single-language, multi-language, and
// skip-upload-selection preference.

import { visitHashRoute, typeInMuiInput, selectMuiMultiDropdownOptions } from '../../support/utils';

describe('Upload Workflow: Synchronous', () => {
  const SOURCE_URL = 'https://en.wikipedia.org/wiki/File:Example.jpg';

  beforeEach(() => {
    cy.stubAppBoot();
    cy.setAuthState(true);
    cy.stubWikimediaFileCheck(false);
    cy.stubUpload('upload/success-sync.json');
    cy.intercept('GET', '**/api/get_wikitext**', { fixture: 'upload/wikitext-template.json' }).as('getWikiText');
    // NOTE: visitHashRoute is called inside each test (not here) so that
    // tests like skip-upload-selection can override intercepts before the
    // first page load.
  });

  it('completes the full 5-step single-language upload → shows result screen with file preview and actions', () => {
    visitHashRoute('/upload');

    // Step 0: Enter source URL
    typeInMuiInput('Enter Source URL', SOURCE_URL);
    cy.contains('button', /next/i).click();

    // Step 1: Project (wikipedia) and Language (en) pre-selected via default preferences
    cy.contains('label', /select project/i).should('be.visible');
    cy.contains('button', /next/i).click();

    // Step 2: Verify target file name was auto-populated from the source URL
    cy.contains('label', /Name of the Target file/i).should('be.visible');
    cy.get('#target-filename-en').should('have.value', 'Example');
    cy.contains('button', /next/i).click();
    cy.wait('@wikimediaFileCheck');

    // Step 3: Template step — checkbox checked by default, textarea has fetched wikitext
    cy.get('textarea').should('be.visible');
    cy.wait('@getWikiText');
    cy.get('textarea').first().invoke('val').should('contain', '== Description ==');
    cy.contains('button', /next/i).click();

    // Step 4: Edit Article step — leave unchecked, click upload
    cy.contains('button', /upload file to target wiki/i).should('be.visible');
    cy.contains('button', /upload file to target wiki/i).click();
    cy.wait('@uploadFile');

    // Result screen: verify upload success toast, file preview, filename in disabled input, and action buttons
    cy.contains('Upload successful').should('be.visible');
    cy.get('img[alt="Uploaded File"]').should('be.visible');
    // The filename is displayed inside a disabled MUI TextField (input value, not text content)
    cy.get('input:disabled').should('have.value', 'TestImage.jpg');
    cy.contains('View Wiki Page').should('be.visible');
    cy.contains('Go Back to Home').should('be.visible');
  });

  it('completes a 2-language upload (en + hi) → result screen shows per-language tabs', () => {
    visitHashRoute('/upload');

    // Override with multi-language success fixture
    cy.stubUpload('upload/success-sync-multi.json');

    // Step 0: Enter source URL
    typeInMuiInput('Enter Source URL', SOURCE_URL);
    cy.contains('button', /next/i).click();

    // Step 1: Add Hindi alongside the pre-selected English
    selectMuiMultiDropdownOptions('Select language', ['हिन्दी']);
    cy.contains('button', /next/i).click();

    // Step 2: Verify language tabs appear for both en and hi
    cy.contains('[role="tab"]', 'ENGLISH').should('be.visible');
    cy.contains('[role="tab"]', 'हिन्दी').should('be.visible');
    // English tab is active by default — verify auto-populated file name
    cy.get('#target-filename-en').should('have.value', 'Example');
    // Switch to Hindi tab and verify the same auto-populated file name
    cy.contains('[role="tab"]', 'हिन्दी').click();
    cy.get('#target-filename-hi').should('have.value', 'Example');
    cy.contains('button', /next/i).click();
    // Wait for file existence checks — one per language
    cy.wait('@wikimediaFileCheck');
    cy.wait('@wikimediaFileCheck');

    // Step 3: Template — advance
    cy.get('textarea').should('be.visible');
    cy.contains('button', /next/i).click();

    // Step 4: Upload
    cy.contains('button', /upload file to target wiki/i).click();
    cy.wait('@uploadFile');

    // Result screen: verify per-language tabs and success content
    cy.contains('[role="tab"]', 'ENGLISH').should('be.visible');
    cy.contains('[role="tab"]', 'हिन्दी').should('be.visible');
    cy.contains('View Wiki Page').should('be.visible');
  });

  it('skip-upload-selection preference jumps from step 0 directly to step 2 → skips project/language selection', () => {
    // Override preferences BEFORE the first page visit so the component
    // picks up skip_upload_selection=true on its initial mount.
    cy.intercept('GET', '**/api/preference', { fixture: 'user/preferences-skip.json' }).as('getPrefs');
    visitHashRoute('/upload');

    // Step 0: Enter URL and click Next
    typeInMuiInput('Enter Source URL', SOURCE_URL);
    cy.contains('button', /next/i).click();

    // Should land on step 2 (Name of Target File), not step 1
    // The target file name label is unique to step 2 content (rendered as <label>)
    cy.contains('label', /Name of the Target file/i).should('be.visible');
    cy.get('#target-filename-en').should('have.value', 'Example');
  });
});