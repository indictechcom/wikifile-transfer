/**
 * Visits a hash route and waits for the layout to mount.
 */
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

/**
 * Helper to type text into a standard MUI text input.
 */
export const typeInMuiInput = (labelText, textToType) => {
  cy.contains('label', labelText)
    .parent()
    .find('input[type="text"]')
    .clear()
    .type(textToType);
};

/**
 * Helper to select options in an MUI multi-select dropdown (checkbox-based).
 * Opens the dropdown, clicks each option, then closes it with Escape.
 */
export const selectMuiMultiDropdownOptions = (labelText, optionTexts) => {
  cy.contains('label', labelText)
    .parent()
    .find('[role="combobox"]')
    .click();

  optionTexts.forEach((text) => {
    cy.get('[role="listbox"] [role="option"]')
      .contains(text)
      .click();
  });

  // Close the multi-select dropdown
  cy.get('body').type('{esc}');
};