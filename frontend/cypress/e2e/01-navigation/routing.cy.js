import { visitHashRoute } from '../../support/utils';

describe('Navigation & Routing', () => {
  beforeEach(() => {
    cy.stubAppBoot();
  });

  it('navigates to the about page', () => {
    visitHashRoute('/about');
    cy.contains('About').should('be.visible');
  });

  it('loads home page and shows welcome text', () => {
    visitHashRoute('/');
    cy.contains('Welcome to the Wikifile-transfer tool page!').should('be.visible');
  });

  it('navigates to 404 page for invalid routes', () => {
    visitHashRoute('/nonexistent');
    cy.contains('404').should('be.visible');
    cy.contains('button', /Back to home/i).click();
    cy.contains('Welcome').should('be.visible');
  });

  it('shows gated tabs when logged out', () => {
    cy.setAuthState(false);
    visitHashRoute('/');
    cy.wait('@getUser');     
    cy.contains('[role="tab"]', /Upload/i).should('not.exist');
    cy.contains('[role="tab"]', /Preference/i).should('not.exist');
  });

  it('shows gated tabs when logged in', () => {
    cy.setAuthState(true);
    visitHashRoute('/');
    cy.wait('@getUser');
    cy.contains('[role="tab"]', /Upload/i).should('be.visible');
    cy.contains('[role="tab"]', /Preference/i).should('be.visible');
  });
});