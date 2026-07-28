import { visitHashRoute } from '../../support/utils';

describe('Authentication UI', () => {
  beforeEach(() => {
    cy.stubAppBoot();
  });

  it('displays correct UI elements when logged out', () => {
    cy.setAuthState(false);
    visitHashRoute('/');
    cy.wait('@getUser');
    
    cy.contains('button', 'Login').should('be.visible');
    cy.get('.MuiAvatar-root').should('not.exist');
    cy.contains('button', 'Login to upload images').should('be.visible');
  });

  it('displays correct UI elements when logged in', () => {
    cy.setAuthState(true, 'WikiAdmin'); 
    visitHashRoute('/');
    cy.wait('@getUser');
    
    cy.get('.MuiAvatar-root').should('contain.text', 'W');
    cy.contains('button', 'Logout').should('be.visible');
    
    cy.contains('button', 'Start uploading').click();
    cy.contains('Enter Source URL').should('be.visible'); 
  });
});