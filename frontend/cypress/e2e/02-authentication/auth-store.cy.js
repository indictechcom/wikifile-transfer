/// <reference types="cypress" />
import { visitHashRoute } from '../../support/utils';

// Do not truncate deep object assertion messages in the command log
chai.config.truncateThreshold = 200;

describe('UI to Redux store', { retries: 2 }, () => {
  // Helper to grab the Redux store from the window
  const getStore = () => cy.window().its('store');
  
  // Helper to grab the exact Redux state
  const getStoreState = () => getStore().invoke('getState');

  beforeEach(() => {
    // Stub API endpoints for app boot
    cy.stubAppBoot();
  });

  context('Initial state and successful loads', () => {
    it('starts with default user state', () => {
      cy.setAuthState(false);
      visitHashRoute('/');
      cy.wait('@getUser');

      getStoreState()
        .its('auth')
        .should('deep.equal', {
          loading: false,
          error: null,
          logged: false,
          username: null,
        });
    });

    it('stores logged-in user in the store', () => {
      cy.setAuthState(true, 'TestUser');
      visitHashRoute('/');
      cy.wait('@getUser');

      getStoreState()
        .its('auth')
        .should('deep.equal', {
          loading: false,
          error: null,
          logged: true,
          username: 'TestUser',
        });
    });
  });

  describe('Delayed network responses', () => {
    it('shows loading state while server response is delayed', () => {
      // force a delayed server response to catch the intermediate loading state
      cy.intercept(
        { method: 'GET', url: '**/api/user' },
        { delay: 3000, body: { logged: true, username: 'SlowUser' } }
      ).as('delayedGetUser');

      visitHashRoute('/');

      // Immediately after visit, before the 3 seconds are up, loading MUST be true
      getStoreState().its('auth.loading').should('equal', true);

      // Wait for the delayed network call to finish
      cy.wait('@delayedGetUser');

      // Now assert the store settled correctly
      getStoreState()
        .its('auth')
        .should('deep.equal', {
          loading: false,
          error: null,
          logged: true,
          username: 'SlowUser',
        });
    });
  });

  describe('Store actions & UI Reactivity', () => {
    it('changes the state on server error', () => {
      // Setup the server to fail
      cy.intercept(
        { method: 'GET', url: '**/api/user' },
        { statusCode: 500, body: 'Internal Server Error' }
      ).as('getUserError');

      visitHashRoute('/');
      cy.wait('@getUserError');

      getStoreState()
        .its('auth')
        .should('deep.equal', {
          loading: false,
          error: 'Internal Server Error', // Captures the error payload
          logged: false,
          username: null,
        });
    });

    it('can be driven by dispatching actions', () => {
      cy.setAuthState(false);
      visitHashRoute('/');
      cy.wait('@getUser');

      // Drive the application by directly dispatching Redux actions
      getStore().invoke('dispatch', {
        type: 'userAuth/setUserSuccess',
        payload: { logged: true, username: 'HackerUser' },
      });

      // Assert the store updated
      getStoreState()
        .its('auth')
        .should('deep.include', {
          logged: true,
          username: 'HackerUser',
        });

      // Drive a reset
      getStore().invoke('dispatch', { type: 'userAuth/resetUser' });

      // Assert the store cleared
      getStoreState().its('auth.username').should('be.null');
    });
  });
});