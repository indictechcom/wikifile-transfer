// Tests the asynchronous (HTTP 202) upload path with per-language
// task polling. Covers PENDING → SUCCESS transitions, FAILURE error
// panels, and PARTIAL success warnings.

import { visitHashRoute, typeInMuiInput } from '../../support/utils';

describe('Upload Workflow: Asynchronous (Polling)', () => {
  const SOURCE_URL = 'https://en.wikipedia.org/wiki/File:AsyncTest.jpg';
  const TASK_ID_EN = 'test-task-en-123';

  beforeEach(() => {
    cy.stubAppBoot();
    cy.setAuthState(true);
    cy.stubWikimediaFileCheck(false);
    cy.intercept('GET', '**/api/get_wikitext**', { fixture: 'upload/wikitext-template.json' }).as('getWikiText');
  });

  /**
   * Navigates through all 5 upload steps and triggers the upload action.
   * Assumes stubs for wikimedia file check, wikitext, and upload are configured.
   */
  const navigateAllStepsAndUpload = () => {
    // Step 0: Enter source URL
    typeInMuiInput('Enter Source URL', SOURCE_URL);
    cy.contains('button', /next/i).click();

    // Step 1: Pre-populated from default preferences (wikipedia, en)
    cy.contains('label', /select project/i).should('be.visible');
    cy.contains('button', /next/i).click();

    // Step 2: Target file name auto-populated from URL
    cy.contains('label', /Name of the Target file/i).should('be.visible');
    cy.contains('button', /next/i).click();
    cy.wait('@wikimediaFileCheck');

    // Step 3: Template — advance
    cy.get('textarea').should('be.visible');
    cy.contains('button', /next/i).click();

    // Step 4: Click upload
    cy.contains('button', /upload file to target wiki/i).click();
    cy.wait('@uploadFile');
  };

  it('polls task status PENDING → SUCCESS → displays result screen', () => {
    cy.stubUpload('upload/success-async-202.json', 202);

    // First poll returns PENDING
    cy.intercept('GET', `**/api/task_status/${TASK_ID_EN}`, {
      fixture: 'upload/task-status-pending.json'
    }).as('taskPending');

    visitHashRoute('/upload');
    navigateAllStepsAndUpload();

    // Wait for the PENDING poll, then switch intercept to SUCCESS
    cy.wait('@taskPending');
    cy.intercept('GET', `**/api/task_status/${TASK_ID_EN}`, {
      fixture: 'upload/task-status-success.json'
    }).as('taskSuccess');

    // Wait for the SUCCESS poll to complete — once all tasks resolve,
    // the next polling interval sets showResult=true and renders results
    cy.wait('@taskSuccess');

    // Result screen should appear with upload details
    cy.contains('View Wiki Page').should('be.visible');
    cy.get('img[alt="Uploaded File"]').should('be.visible');
  });

  it('displays failure panel when async task returns FAILURE status', () => {
    cy.stubUpload('upload/success-async-202.json', 202);

    // Return FAILURE on the first poll
    cy.intercept('GET', `**/api/task_status/${TASK_ID_EN}`, {
      fixture: 'upload/task-status-failure.json'
    }).as('taskFailed');

    visitHashRoute('/upload');
    navigateAllStepsAndUpload();

    // Wait for the FAILURE poll
    cy.wait('@taskFailed');

    // Verify the red failure error panel is rendered
    cy.contains('Upload failed').should('be.visible');
    cy.contains('Upload processing failed: file too large').should('be.visible');
  });

  it('displays partial-success warning when async task returns PARTIAL status', () => {
    cy.stubUpload('upload/success-async-202.json', 202);

    // Return PARTIAL on the first poll
    cy.intercept('GET', `**/api/task_status/${TASK_ID_EN}`, {
      fixture: 'upload/task-status-partial.json'
    }).as('taskPartial');

    visitHashRoute('/upload');
    navigateAllStepsAndUpload();

    // Wait for the PARTIAL poll
    cy.wait('@taskPartial');

    // Verify partial success warning panel and the underlying success content
    cy.contains('Partial success').should('be.visible');
    cy.contains('Template could not be applied').should('be.visible');
    // File preview should still be rendered below the warning
    cy.get('img[alt="Uploaded File"]').should('be.visible');
  });

  it('displays processing uploads intermediate view with per-language progress cards during async upload', () => {
    cy.stubUpload('upload/success-async-202.json', 202);

    // Return PENDING status on first poll
    cy.intercept('GET', `**/api/task_status/${TASK_ID_EN}`, {
      fixture: 'upload/task-status-pending.json'
    }).as('taskPending');

    visitHashRoute('/upload');
    navigateAllStepsAndUpload();

    // The processing uploads intermediate view should be displayed
    // while tasks are still pending (before results are final)
    cy.contains('Processing uploads').should('be.visible');

    // Verify per-language progress card is rendered with the language name
    cy.contains('ENGLISH').should('be.visible');

    // Verify progress indicator (LinearProgress) is present
    cy.get('[role="progressbar"]').should('exist');

    // Wait for the pending poll to complete
    cy.wait('@taskPending');

    // Switch to SUCCESS so the test can cleanly resolve
    cy.intercept('GET', `**/api/task_status/${TASK_ID_EN}`, {
      fixture: 'upload/task-status-success.json'
    }).as('taskSuccess');

    cy.wait('@taskSuccess');

    // After all tasks resolve, result screen should replace the progress view
    cy.contains('View Wiki Page').should('be.visible');
  });
});