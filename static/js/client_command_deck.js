// Keep the full command deck in one row and scale its box and hit targets together.
(() => {
  const deck = document.getElementById("client-command-deck");
  const frame = deck?.parentElement;
  if (!frame?.classList.contains("client-command-frame")) return;

  function fitCommandDeck() {
    const available = frame.clientWidth;
    if (!available) return;
    const width = Math.max(980, available);
    const scale = available / width;
    deck.style.width = `${width}px`;
    deck.style.transform = `scale(${scale})`;
    const height = Math.ceil(deck.offsetHeight * scale);
    if (frame.style.height !== `${height}px`) {
      frame.style.height = `${height}px`;
      if (typeof scheduleBoardRecovery === "function") scheduleBoardRecovery(0);
    }
  }

  fitCommandDeck();
  window.addEventListener("resize", fitCommandDeck);
  window.addEventListener("load", fitCommandDeck);
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(fitCommandDeck).observe(frame);
})();
