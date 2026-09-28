/* On-screen annotations for the walkthrough recording.
 *
 * Injected into the page and drawn in the DOM, so Playwright's own recorder
 * captures them with everything else — no compositing pass afterwards, and the
 * highlight tracks the element even if the layout shifts.
 *
 * Everything lives under one root that is wiped between steps, so a step can
 * never leave a stale label on screen for the next one.
 */
(() => {
  const ID = "sutra-walkthrough-layer";
  if (document.getElementById(ID)) return;

  const css = `
    #${ID}{position:fixed;inset:0;z-index:2147483647;pointer-events:none;
      font-family:"Segoe UI",system-ui,sans-serif}
    #${ID} .wt-badge{position:absolute;top:22px;left:50%;transform:translateX(-50%);
      background:rgba(9,16,28,.94);border:1px solid rgba(240,164,40,.55);
      border-radius:8px;padding:9px 18px;display:flex;align-items:center;gap:12px;
      box-shadow:0 8px 28px rgba(0,0,0,.55)}
    #${ID} .wt-ref{color:#F0A428;font-weight:700;font-size:15px;letter-spacing:.6px;
      font-variant-numeric:tabular-nums}
    #${ID} .wt-title{color:#EAF0F7;font-size:15px;font-weight:600}
    #${ID} .wt-ring{position:absolute;border:3px solid #F0A428;border-radius:8px;
      box-shadow:0 0 0 3px rgba(240,164,40,.22),0 0 22px rgba(240,164,40,.45);
      animation:wt-pulse 1.5s ease-in-out infinite}
    @keyframes wt-pulse{0%,100%{opacity:1}50%{opacity:.55}}
    #${ID} .wt-note{position:absolute;background:#F0A428;color:#0B1522;
      font-size:14px;font-weight:700;padding:6px 12px;border-radius:6px;
      white-space:nowrap;box-shadow:0 4px 14px rgba(0,0,0,.45)}
    #${ID} .wt-verdict{position:absolute;bottom:120px;left:50%;
      transform:translateX(-50%);padding:10px 22px;border-radius:8px;
      font-size:16px;font-weight:700;letter-spacing:.3px;
      box-shadow:0 8px 24px rgba(0,0,0,.5)}
    #${ID} .wt-pass{background:rgba(24,74,48,.96);color:#5BE08A;
      border:1px solid rgba(91,224,138,.5)}
    #${ID} .wt-fail{background:rgba(88,26,26,.96);color:#FF8A8A;
      border:1px solid rgba(255,138,138,.5)}
  `;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  const root = document.createElement("div");
  root.id = ID;
  document.body.appendChild(root);

  const el = (cls, text) => {
    const d = document.createElement("div");
    d.className = cls;
    if (text != null) d.textContent = text;
    return d;
  };

  window.wt = {
    /** Step banner: the test reference and what is being proved. */
    badge(ref, title) {
      root.querySelectorAll(".wt-badge").forEach((n) => n.remove());
      const b = el("wt-badge");
      b.appendChild(el("wt-ref", ref));
      b.appendChild(el("wt-title", title));
      root.appendChild(b);
    },

    /** Ring a live element, optionally with a pointer label beside it. */
    ring(selector, note) {
      const t = document.querySelector(selector);
      if (!t) return false;
      const r = t.getBoundingClientRect();
      if (!r.width || !r.height) return false;
      const pad = 6;
      const ring = el("wt-ring");
      Object.assign(ring.style, {
        left: `${r.left - pad}px`, top: `${r.top - pad}px`,
        width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px`,
      });
      root.appendChild(ring);
      if (note) {
        const n = el("wt-note", note);
        root.appendChild(n);
        // prefer sitting under the target; flip above when it would fall off
        const nb = n.getBoundingClientRect();
        const below = r.bottom + 12 + nb.height < window.innerHeight;
        n.style.top = below ? `${r.bottom + 12}px` : `${r.top - nb.height - 12}px`;
        n.style.left = `${Math.max(12, Math.min(window.innerWidth - nb.width - 12,
                                               r.left + r.width / 2 - nb.width / 2))}px`;
      }
      return true;
    },

    /** The result of the check, stated on screen rather than implied. */
    verdict(ok, text) {
      root.querySelectorAll(".wt-verdict").forEach((n) => n.remove());
      root.appendChild(el(`wt-verdict ${ok ? "wt-pass" : "wt-fail"}`,
                          (ok ? "PASS  ✓  " : "ISSUE  ✗  ") + text));
    },

    /** Drop rings, labels and verdicts; the badge is cleared by the next badge. */
    clear() {
      root.querySelectorAll(".wt-ring,.wt-note,.wt-verdict").forEach((n) => n.remove());
    },

    reset() {
      root.innerHTML = "";
    },
  };
})();
