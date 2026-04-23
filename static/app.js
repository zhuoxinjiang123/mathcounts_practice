document.addEventListener("input", (event) => {
  if (!event.target.matches(".answer-row input")) {
    return;
  }
  event.target.value = event.target.value.replace(/\s+/g, " ").trimStart();
});
