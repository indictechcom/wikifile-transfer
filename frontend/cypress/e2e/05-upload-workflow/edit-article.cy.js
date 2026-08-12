// Tests the Edit Article feature across step 4 of the upload workflow
// and the post-upload Edit Article section on the results page.

import { visitHashRoute, typeInMuiInput } from '../../support/utils';

describe('Upload Workflow: Edit Article', () => {
  const SOURCE_URL = 'https://en.wikipedia.org/wiki/File:EditTest.jpg';

  beforeEach(() => {
    cy.stubAppBoot();
    cy.setAuthState(true);
    cy.stubWikimediaFileCheck(false);
    cy.intercept('GET', '**/api/get_wikitext**', { fixture: 'upload/wikitext-template.json' }).as('getWikiText');
  });

  /**
   * Navigates from step 0 through step 3 (source URL → project/language → target filename → template).
   * Leaves the test at step 4 (Edit Article).
   */
  const navigateToStep4 = () => {
    typeInMuiInput('Enter Source URL', SOURCE_URL);
    cy.contains('button', /next/i).click();

    // Step 1: pre-populated from default preferences
    cy.contains('label', /select project/i).should('be.visible');
    cy.contains('button', /next/i).click();

    // Step 2: target filename auto-populated
    cy.contains('label', /Name of the Target file/i).should('be.visible');
    cy.contains('button', /next/i).click();
    cy.wait('@wikimediaFileCheck');

    // Step 3: template — advance
    cy.get('textarea').should('be.visible');
    cy.contains('button', /next/i).click();
  };

  it('enables article link input when Edit Article checkbox is checked on step 4', () => {
    visitHashRoute('/upload');
    navigateToStep4();

    // Step 4: Verify the Edit Article checkbox is present and unchecked by default
    // The TextField for target article name should be disabled when unchecked
    cy.get('input[type="checkbox"]').should('not.be.checked');
    // The article name input should be disabled
    cy.get('input').filter(':disabled').should('exist');

    // Check the Edit Article checkbox
    cy.get('input[type="checkbox"]').check();

    // After checking, the article link TextField should now be enabled
    // We can't check by id since EditArticleStep doesn't set one, use the label
    cy.contains('label', /target-article-name|Target article/i)
      .parent()
      .find('input')
      .should('not.be.disabled');
  });

  it('disables article link input when Edit Article checkbox is unchecked', () => {
    visitHashRoute('/upload');
    navigateToStep4();

    // Check then uncheck the Edit Article checkbox
    cy.get('input[type="checkbox"]').check();
    cy.get('input[type="checkbox"]').uncheck();

    // Article link input should be disabled again
    cy.contains('label', /target-article-name|Target article/i)
      .parent()
      .find('input')
      .should('be.disabled');
  });

  it('displays Edit Article section on results page when editArticle was opted in', () => {
    // Use the fixture that includes wikitext_fetch_success
    cy.stubUpload('upload/success-sync-with-wikitext.json');
    visitHashRoute('/upload');
    navigateToStep4();

    // Step 4: Check Edit Article and enter an article name
    cy.get('input[type="checkbox"]').check();
    cy.contains('label', /target-article-name|Target article/i)
      .parent()
      .find('input')
      .clear()
      .type('Test_Article');

    // Click upload
    cy.contains('button', /upload file to target wiki/i).click();
    cy.wait('@uploadFile');

    // Result screen should show the Edit Article card
    cy.contains('Edit article').should('be.visible');
    // The article wikitext textarea should contain the fetched wikitext
    cy.get('textarea').should('be.visible');
    cy.get('textarea').invoke('val').should('contain', '== Description ==');
    // Save Changes button should be present
    cy.contains('button', /save-changes/i).should('be.visible');
  });

  it('successfully edits article via Save Changes button → shows success alert', () => {
    cy.stubUpload('upload/success-sync-with-wikitext.json');
    // Stub the edit article API
    cy.intercept('POST', '**/api/edit_article', {
      statusCode: 200,
      body: { success: true, data: {}, errors: [] }
    }).as('editArticle');

    visitHashRoute('/upload');
    navigateToStep4();

    // Step 4: Enable Edit Article and enter article name
    cy.get('input[type="checkbox"]').check();
    cy.contains('label', /target-article-name|Target article/i)
      .parent()
      .find('input')
      .clear()
      .type('Test_Article');

    cy.contains('button', /upload file to target wiki/i).click();
    cy.wait('@uploadFile');

    // On the results page, click Save Changes
    cy.contains('button', /save-changes/i).click();
    cy.wait('@editArticle');

    // Verify the edit article request payload
    cy.get('@editArticle').its('request.body').should('deep.include', {
      articleName: 'Test_Article',
      lang: 'en',
      project: 'wikipedia'
    });

    // Success alert should appear
    cy.get('[role="alert"]').contains(/article.*success/i).should('be.visible');
  });

  it('shows error toast when article edit fails', () => {
    cy.stubUpload('upload/success-sync-with-wikitext.json');
    // Stub the edit article API to fail
    cy.intercept('POST', '**/api/edit_article', {
      statusCode: 500,
      body: { success: false, data: {}, errors: ['Edit Error'] }
    }).as('editArticleFail');

    visitHashRoute('/upload');
    navigateToStep4();

    // Step 4: Enable Edit Article and enter article name
    cy.get('input[type="checkbox"]').check();
    cy.contains('label', /target-article-name|Target article/i)
      .parent()
      .find('input')
      .clear()
      .type('Test_Article');

    cy.contains('button', /upload file to target wiki/i).click();
    cy.wait('@uploadFile');

    // On the results page, click Save Changes
    cy.contains('button', /save-changes/i).click();
    cy.wait('@editArticleFail');

    // Error toast should appear
    cy.contains('An error occurred while editing the article').should('be.visible');
  });
});
