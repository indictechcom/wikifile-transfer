/// <reference types="cypress" />

declare namespace Cypress {
  interface Chainable<Subject> {
    /**
     * Simulates a logged-in or logged-out user via /api/user.
     */
    setAuthState(isLoggedIn?: boolean, username?: string): Chainable<{ logged: boolean, username: string | null }>;
    
    /**
     * Intercepts all default API endpoints required for app boot using fixtures.
     * Stubs /api/preference as @getPrefs, /api/user_language as @getLang, and defaults auth to logged-out.
     */
    stubAppBoot(): Chainable<any>;

    /**
     * Stubs the polling Celery task endpoint.
     * Alias: @getTaskStatus
     */
    stubTaskStatus(taskId: string, fixturePath: string): Chainable<any>;

    /**
     * Stubs the /api/upload endpoint
     * Alias: @uploadFile
     */
    stubUpload(fixturePath: string, statusCode?: number): Chainable<any>;
    
    /**
     * Stubs the external Wikimedia API check for file existence
     * Alias: @wikimediaFileCheck
     */
    stubWikimediaFileCheck(exists?: boolean): Chainable<any>;
  }
}

declare module '*/cypress/support/utils' {
  export function visitHashRoute(route?: string): void;
  export function selectMuiDropdown(labelText: string, optionText: string): void;
  export function typeInMuiInput(labelText: string, textToType: string): void;
}