import { visitHashRoute, typeInMuiInput } from '../../support/utils';

describe('Upload Workflow: Asynchronous (Polling)', () => {
  const URL = 'https://en.wikipedia.org/wiki/File:Massive_File.jpg';
  const TASK_ID = 'test-task-123';

  beforeEach(() => {
    cy.stubAppBoot();
    cy.setAuthState(true);
    cy.stubWikimediaFileCheck(false);
    cy.intercept('GET', '**/api/preference', { fixture: 'user/preferences-skip.json' });
    cy.stubUpload('upload/success-async-202.json', 202);
    cy.intercept('GET', '**/api/get_wikitext**', { fixture: 'upload/wikitext-template.json' }).as('getWikitext');
  });

  it('polls task status until SUCCESS and transitions to Step 4', () => {
    visitHashRoute('/upload');

    // Due to preferences-skip.json, this will jump directly from Step 1 to Step 3
    typeInMuiInput('Source URL', URL);
    cy.contains('button', /Next/i).click();
    
    cy.contains('Name of the Target file').should('be.visible');
    
    // 1st Poll -> Pending
    cy.stubTaskStatus(TASK_ID, 'upload/task-status-pending.json');
    cy.contains('button', /Upload file/i).click();
    cy.get('[role="progressbar"]').should('be.visible');

    // 2nd Poll -> Success
    cy.stubTaskStatus(TASK_ID, 'upload/task-status-success.json');
    
    cy.wait('@getWikitext');
    cy.get('textarea').first().should('exist'); 
  });
});