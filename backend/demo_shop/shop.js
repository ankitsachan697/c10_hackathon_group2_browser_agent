"use strict";
// This is a deliberately synthetic target, not an authentication/payment service.
const scenario = JSON.parse(document.getElementById("scenario").textContent);
const byId = id => document.getElementById(id);
const accounts = new Map([["demo@example.test", "DemoPass123!"]]);
let quantity = 0;
function showStage(name) {
  for (const stage of ["account", "shop", "cart", "checkout", "confirmation"]) {
    byId(stage).hidden = stage !== name;
    byId(`stage-${stage}`).classList.toggle("active", stage === name);
  }
  byId("sign-out").hidden = name === "account";
}
function switchAccount(register) {
  byId("login-form").hidden = register;
  byId("registration-form").hidden = !register;
  byId("login-tab").classList.toggle("active", !register);
  byId("register-tab").classList.toggle("active", register);
  byId("auth-error").hidden = true;
}
function authError(message) { byId("auth-error").textContent = message; byId("auth-error").hidden = false; }
byId("login-tab").onclick = () => switchAccount(false);
byId("register-tab").onclick = () => switchAccount(true);
byId("login-form").onsubmit = event => {
  event.preventDefault();
  if (accounts.get(byId("username").value.trim()) !== byId("password").value) return authError("Invalid credentials. Please try again.");
  byId("password").value = "";
  byId("auth-error").hidden = true;
  quantity = 0;
  byId("cart-feedback").hidden = true;
  showStage("shop");
};
byId("registration-form").onsubmit = event => {
  event.preventDefault();
  const email = byId("registration-email").value.trim();
  if (accounts.has(email)) return authError("An account with this email already exists.");
  accounts.set(email, byId("registration-password").value);
  byId("registration-password").value = "";
  byId("username").value = email;
  byId("account-success").textContent = "Account created. Please sign in.";
  byId("account-success").hidden = false;
  switchAccount(false);
};
byId("add-to-cart").onclick = () => { quantity += 1; byId("cart-feedback").hidden = false; };
byId("view-cart").onclick = () => {
  if (!quantity) { byId("cart-feedback").textContent = "Add an item before opening your cart."; byId("cart-feedback").hidden = false; return; }
  byId("quantity").textContent = String(quantity);
  for (const id of ["cart-total", "checkout-total", "order-total"]) byId(id).textContent = `$${(quantity * 24).toFixed(2)}`;
  showStage("cart");
};
byId("checkout-button").onclick = () => showStage("checkout");
if (scenario.locator_revision) {
  // Same business action, changed accessible name and identifier: saved locators go stale.
  const button = byId("checkout-button");
  button.textContent = "Continue to shipping";
  button.id = "shipping-next";
}
byId("back-to-shop").onclick = () => showStage("shop");
byId("checkout-form").onsubmit = event => {
  event.preventDefault();
  byId("checkout-error").hidden = !scenario.checkout_failure;
  if (scenario.checkout_failure) { byId("checkout-error").textContent = "Checkout unavailable: inventory service rejected the order."; return; }
  showStage("confirmation");
};
byId("sign-out").onclick = () => { quantity = 0; byId("login-form").reset(); byId("checkout-form").reset(); byId("account-success").hidden = true; showStage("account"); };
document.body.classList.toggle("visual-change", scenario.visual_variant);
showStage("account");
switchAccount(false);
