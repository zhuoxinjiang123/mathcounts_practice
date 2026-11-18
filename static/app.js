document.addEventListener("input", (event) => {
  if (!event.target.matches(".answer-row input")) {
    return;
  }
  event.target.value = event.target.value.replace(/\s+/g, " ").trimStart();
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!form.matches(".generate-form")) {
    return;
  }
  const button = form.querySelector("button");
  if (button) {
    button.disabled = true;
    button.textContent = "Starting…";
  }
});
