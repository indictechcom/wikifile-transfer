export const visitHashRoute = (route = '/') => {
  cy.visit(`/#${route}`);
  // Wait for the main layout to mount
  cy.get('.MuiContainer-root').should('be.visible');
};

/**
 * Helper to bypass MUI Select's hidden native input and portal behavior.
 */
export const selectMuiDropdown = (labelText, optionText) => {
  cy.contains('label', labelText)
    .parent()
    .find('[role="combobox"]')
    .click();
  
  // MUI Select renders options in a portal at the bottom of the DOM
  cy.get('[role="listbox"] [role="option"]')
    .contains(optionText)
    .click();
};

export const typeInMuiInput = (labelText, textToType) => {
  cy.contains('label', labelText)
    .parent()
    .find('input[type="text"]')
    .clear()
    .type(textToType);
};