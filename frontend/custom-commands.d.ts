/// <reference types="cypress" />

declare namespace Cypress {
  interface Chainable<Subject> {
    /**
     * Simulates a logged-in or logged-out user via /api/user.
     */
    setAuthState(isLoggedIn?: boolean, username?: string): Chainable<any>;
    
    /**
     * Intercepts all default API endpoints required for app boot using fixtures.
     */
    stubAppBoot(): Chainable<any>;

    /**
     * Stubs the polling Celery task endpoint.
     */
    stubTaskStatus(taskId: string, fixturePath: string): Chainable<any>;

    /**
     * Stubs the /api/upload endpoint
     */
    stubUpload(fixturePath: string, statusCode?: number): Chainable<any>;
    
    /**
     * Stubs the external Wikimedia API check for file existence
     */
    stubWikimediaFileCheck(exists?: boolean): Chainable<any>;
  }
}