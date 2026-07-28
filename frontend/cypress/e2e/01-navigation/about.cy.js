import { visitHashRoute } from '../../support/utils';

describe('About Page', () => {
  beforeEach(() => {
    cy.stubAppBoot();
    visitHashRoute('/about');
  });

  it('displays the about page heading', () => {
    cy.contains('h4', /about/i).should('be.visible');
  });

  it('shows author information', () => {
    cy.contains('Jay Pakash').should('be.visible');
    cy.contains('Sarthak Parashar').should('be.visible');
  });

  it('contains a link to the GitHub repository', () => {
    cy.contains('a', /github/i)
      .should('have.attr', 'href')
      .and('include', 'github.com/indictechcom/wikifile-transfer');
  });

  it('contains a link to the meta wiki page', () => {
    cy.contains('a', /learn more/i)
      .should('have.attr', 'href')
      .and('include', 'meta.wikimedia.org');
  });
});
