import { visitHashRoute, typeInMuiInput, selectMuiDropdown } from '../../support/utils';

describe('Upload Workflow: Synchronous', () => {
  const URL = 'https://en.wikipedia.org/wiki/File:Example.jpg';

  beforeEach(() => {
    cy.stubAppBoot();
    cy.setAuthState(true);
    cy.stubWikimediaFileCheck(false);
    cy.stubUpload('upload/success-sync.json');
    cy.intercept('GET', '**/api/get_wikitext**', { fixture: 'upload/wikitext-template.json' }).as('getWikiText');
    cy.intercept('POST', '**/api/edit_page', { statusCode: 200 }).as('editPage');
    
    visitHashRoute('/upload');
  });

  it('completes the full 4-step upload process', () => {
    typeInMuiInput('Source URL', URL);
    cy.contains('button', /Next/i).click();

    selectMuiDropdown('Select project', 'Wiktionary');
    cy.contains('button', /Next/i).click();

    cy.get('input[type="text"]').last().should('have.value', 'Example');
    cy.contains('button', /Upload file/i).click();

    cy.wait('@getWikiText');
    cy.get('textarea').first().should('contain.text', '== Description ==');
    
    cy.contains('button', 'Finish with edit').click();
    cy.wait('@editPage');
    cy.contains('View Wiki Page').should('be.visible');
  });
});