/**
 * Builds the SUTRA Solution Presentation (hackathon submission deliverable 1).
 *
 * Content is drawn from docs/HLD.md and from figures measured against the
 * running platform, so the deck and the technical proposal cannot drift apart.
 * Regenerate with:  node scripts/build_presentation.js
 */

const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5 — set before any slide is added
pres.author = "Lavesh Paryani";
pres.title = "SUTRA — Statewide Unified Tracking, Registry & Analytics";

// Control-room palette, matching the platform's own dark tactical UI: the deck
// should look like the product it describes, not like a generic template.
const INK = "0E1A2B"; // deep navy — dominant
const INK_2 = "16263C"; // raised panel
const AMBER = "F0A428"; // the UI's accent, used sparingly
const ICE = "CBD8E8"; // body text on dark
const MUTE = "8A9BB0"; // captions
const WHITE = "FFFFFF";
const GREEN = "3FAE6A";
const RED = "C94F4F";

const H_FONT = "Cambria"; // safe-list serif for headings
const B_FONT = "Calibri"; // safe-list sans for body

/** Numbered amber disc — the deck's one repeated motif. */
function disc(slide, n, x, y, size = 0.42) {
  slide.addShape(pres.ShapeType.ellipse, {
    x, y, w: size, h: size, fill: { color: AMBER },
  });
  slide.addText(String(n), {
    x, y, w: size, h: size, align: "center", valign: "middle",
    fontSize: 13, bold: true, color: INK, fontFace: B_FONT, isTextBox: true, margin: 0,
  });
}

/** Dark content slide with a title, returning the y where content may start. */
function darkSlide(title, kicker) {
  const s = pres.addSlide();
  s.background = { color: INK };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: 0.6, y: 0.42, w: 12.1, h: 0.3, fontSize: 11, bold: true,
      color: AMBER, charSpacing: 2, fontFace: B_FONT, isTextBox: true, margin: 0,
    });
  }
  s.addText(title, {
    x: 0.6, y: kicker ? 0.72 : 0.55, w: 12.1, h: 0.75,
    fontSize: 32, bold: true, color: WHITE, fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  return s;
}

/** Rounded panel — tint and shadow for separation, never an edge stripe. */
function panel(slide, x, y, w, h, fill = INK_2) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.08, fill: { color: fill },
    shadow: { type: "outer", color: "000000", blur: 10, offset: 2, angle: 90, opacity: 0.35 },
  });
}

/* ------------------------------------------------------------------ 1 title */
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("SUTRA", {
    x: 0.9, y: 1.85, w: 8.4, h: 1.5, fontSize: 82, bold: true,
    color: WHITE, fontFace: H_FONT, charSpacing: 6, isTextBox: true, margin: 0,
  });
  s.addText("Statewide Unified Tracking, Registry & Analytics", {
    x: 0.95, y: 3.3, w: 9.5, h: 0.5, fontSize: 19, color: AMBER,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  s.addText(
    "A unified platform federating 26 departments' CCTV systems — registry and GIS, " +
    "AI number-plate analytics, government-database correlation and real-time alerting.",
    { x: 0.95, y: 3.95, w: 8.2, h: 0.9, fontSize: 14, color: ICE, lineSpacing: 22,
      fontFace: B_FONT, isTextBox: true, margin: 0 }
  );
  s.addText(
    [
      { text: "Gujarat Police CCTV Integration Hackathon 2026", options: { bold: true, breakLine: true } },
      { text: "Category 1 · Individual entry · Lavesh Paryani", options: { breakLine: true } },
      { text: "Hybrid architecture: Model 1 (mandatory) + Model 3", options: {} },
    ],
    { x: 0.95, y: 5.25, w: 8.2, h: 1.1, fontSize: 13, color: MUTE, lineSpacing: 20,
      fontFace: B_FONT, isTextBox: true, margin: 0 }
  );
  // running-platform proof, stated up front
  panel(s, 9.9, 1.9, 2.9, 3.6);
  s.addText("RUNNING NOW", {
    x: 10.15, y: 2.15, w: 2.4, h: 0.25, fontSize: 10, bold: true, color: AMBER,
    charSpacing: 1.5, fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  const facts = [
    ["38", "cameras onboarded"],
    ["11", "districts · 7 departments"],
    ["59", "automated tests green"],
    ["17/17", "live API endpoints"],
  ];
  facts.forEach(([big, small], i) => {
    const y = 2.55 + i * 0.72;
    s.addText(big, { x: 10.15, y, w: 2.4, h: 0.36, fontSize: 25, bold: true,
      color: WHITE, fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(small, { x: 10.15, y: y + 0.34, w: 2.4, h: 0.24, fontSize: 10.5,
      color: MUTE, fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  s.addNotes(
    "SUTRA is a working platform, not a proposal. Hosted instance is live with real " +
    "accumulated data from the hackathon portal's government feeds."
  );
}

/* ------------------------------------------------------- 2 problem framing */
{
  const s = darkSlide("Twenty-six departments, twenty-six islands", "The problem");
  const items = [
    ["Heterogeneous infrastructure", "Analog and IP cameras, multiple VMS vendors, differing AMC periods, formats and feed protocols — no common contract."],
    ["Geographic dispersion", "Sites up to ~1,000 km apart on constrained, shared links. Bandwidth, not compute, is the binding limit."],
    ["No unified analytics", "Each department watches its own screens. A vehicle crossing departmental boundaries crosses an information gap."],
    ["Scale without redesign", "New cameras, departments and analytics must onboard continuously — toward ~80,000 cameras."],
  ];
  items.forEach(([h, b], i) => {
    const x = 0.6 + (i % 2) * 6.3;
    const y = 1.85 + Math.floor(i / 2) * 2.35;
    panel(s, x, y, 5.9, 2.05);
    disc(s, i + 1, x + 0.32, y + 0.32);
    s.addText(h, { x: x + 0.95, y: y + 0.3, w: 4.6, h: 0.4, fontSize: 16, bold: true,
      color: WHITE, fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(b, { x: x + 0.32, y: y + 0.92, w: 5.25, h: 0.95, fontSize: 12,
      color: ICE, lineSpacing: 18, fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  s.addNotes("These four constraints drive every architectural decision that follows.");
}

/* --------------------------------------------------- 3 model justification */
{
  const s = darkSlide("Federate metadata, not video", "Chosen model");
  s.addText("Hybrid: Model 1 (Registry & GIS, mandatory) + Model 3 (VMS Federation Middleware)", {
    x: 0.6, y: 1.6, w: 12.1, h: 0.35, fontSize: 15, bold: true, color: AMBER,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  const rows = [
    ["Model 1 is load-bearing, not a checkbox", "Scheduling, alerting, route reconstruction and gap analysis all key off registry metadata. It is the spine, not an inventory."],
    ["Model 3 over Model 2", "26 departments will never converge on one VMS. An adapter layer federating sources and databases behind stable interfaces is the only design that survives vendor churn — departments keep their infrastructure and control."],
    ["Not Model 4 as the primary posture", "Centralising 80,000 video streams is a bandwidth and cost trap. SUTRA centralises metadata and evidence: kilobytes per camera-minute instead of megabits per second."],
  ];
  rows.forEach(([h, b], i) => {
    const y = 2.2 + i * 1.6;
    panel(s, 0.6, y, 12.1, 1.4);
    disc(s, i + 1, 0.92, y + 0.3);
    s.addText(h, { x: 1.55, y: y + 0.26, w: 10.8, h: 0.38, fontSize: 15.5, bold: true,
      color: WHITE, fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(b, { x: 1.55, y: y + 0.68, w: 10.8, h: 0.6, fontSize: 12, color: ICE,
      lineSpacing: 17, fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  s.addNotes("The 500x bandwidth argument is quantified on the scalability slide.");
}

/* ------------------------------------------------------------ 4 architecture */
{
  const s = darkSlide("Five modules, one contract each", "Architecture");
  const mods = [
    ["COMMAND", "React + Leaflet control room", "Overview map · video wall · vehicle trace · alert centre · registry · coverage analysis · audit", AMBER],
    ["ATLAS", "Registry & GIS foundation (Model 1)", "Bulk/API/manual onboarding · layered GIS map · camera health · gap & ageing analysis · CSV export · audit trail", "5B8FB9"],
    ["BRIDGE", "Source adapters & federation (Model 3)", "http-progressive · RTSP over TCP · file · HLS/ONVIF-ready · adaptive ingest scheduler · shared MJPEG relay", "5B8FB9"],
    ["INSIGHT", "AI video analytics", "YOLOv9-t plate detection → CCT-S OCR → temporal voting → Indian-plate normalisation · YOLOX-nano scene analytics · route reconstruction", "5B8FB9"],
    ["WATCH", "Watchlist correlation & alerting", "Fuzzy matcher · severity model · WebSocket push · gov-DB connectors (VAHAN / SARTHI / eGujCop / AFIS contract)", "5B8FB9"],
  ];
  mods.forEach(([name, sub, body, col], i) => {
    const y = 1.72 + i * 1.02;
    panel(s, 0.6, y, 12.1, 0.9);
    s.addText(name, { x: 0.92, y: y + 0.16, w: 1.9, h: 0.32, fontSize: 15, bold: true,
      color: col, fontFace: H_FONT, charSpacing: 1, isTextBox: true, margin: 0 });
    s.addText(sub, { x: 0.92, y: y + 0.5, w: 3.1, h: 0.3, fontSize: 10.5, color: MUTE,
      fontFace: B_FONT, isTextBox: true, margin: 0 });
    s.addText(body, { x: 4.2, y: y + 0.2, w: 8.2, h: 0.6, fontSize: 11.5, color: ICE,
      lineSpacing: 16, fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  s.addText("Every module above is running code, demonstrated on the hackathon portal's live feeds — not a proposed component.", {
    x: 0.6, y: 6.88, w: 12.1, h: 0.3, fontSize: 11, italic: true, color: AMBER,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
}

/* ------------------------------------------------------------- 5 ANPR stack */
{
  const s = darkSlide("Reading Indian plates on a CPU", "AI analytics");
  const stages = [
    ["Detect", "YOLOv9-tiny 640 (ONNX), 8 MB", "30–75 ms/frame"],
    ["Read", "CCT-S v2 (ONNX), 5 MB", "per-character probabilities"],
    ["Vote", "Per-vehicle track, char-level probability vote", "absorbs partial reads"],
    ["Normalise", "Structure-aware confusion repair, state-code validation", "against the official code list"],
  ];
  stages.forEach(([h, b, c], i) => {
    const x = 0.6 + i * 3.08;
    panel(s, x, 1.8, 2.85, 2.0);
    disc(s, i + 1, x + 0.28, 2.05, 0.38);
    s.addText(h, { x: x + 0.78, y: 2.03, w: 1.9, h: 0.34, fontSize: 16, bold: true,
      color: WHITE, fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(b, { x: x + 0.28, y: 2.55, w: 2.3, h: 0.8, fontSize: 11.5, color: ICE,
      lineSpacing: 16, fontFace: B_FONT, isTextBox: true, margin: 0 });
    s.addText(c, { x: x + 0.28, y: 3.35, w: 2.3, h: 0.28, fontSize: 10, italic: true,
      color: AMBER, fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  panel(s, 0.6, 4.1, 12.1, 2.15);
  s.addText("Honest accuracy characterisation", {
    x: 0.95, y: 4.32, w: 11.4, h: 0.34, fontSize: 15, bold: true, color: AMBER,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText(
    [
      { text: "Close-range cameras (toll gates, showroom approaches) read at 0.81–0.98 confidence.", options: { bullet: true, breakLine: true } },
      { text: "Wide-angle intersection PTZs yield 50–90 px plates — partial reads the voting and fuzzy layers absorb.", options: { bullet: true, breakLine: true } },
      { text: "Two-line commercial plates produce OCR variants; investigators register variants under one FIR.", options: { bullet: true, breakLine: true } },
      { text: "A fuzzy hit is labelled probable and shows the raw read — an operator is never handed an inference as a certainty.", options: { bullet: true } },
    ],
    { x: 0.95, y: 4.72, w: 11.4, h: 1.4, fontSize: 12, color: ICE, paraSpaceAfter: 6,
      fontFace: B_FONT, isTextBox: true, margin: 0 }
  );
  s.addNotes("Scene analytics (YOLOX-nano, 43 ms/frame) adds person/vehicle counts per camera as a throttled sidecar.");
}

/* ------------------------------------------- 6 watchlist correlation + alerts */
{
  const s = darkSlide("From a read to an operational reaction", "Watchlist & alerting");
  const flow = ["Finalised read", "Exact / fuzzy match", "Alert + evidence", "Scheduler boost"];
  flow.forEach((t, i) => {
    const x = 0.6 + i * 3.15;
    panel(s, x, 1.75, 2.75, 0.72, i === 3 ? "24405E" : INK_2);
    s.addText(t, { x, y: 1.75, w: 2.75, h: 0.72, align: "center", valign: "middle",
      fontSize: 13, bold: true, color: i === 3 ? AMBER : WHITE, fontFace: B_FONT,
      isTextBox: true, margin: 0 });
    if (i < 3) {
      s.addText("→", { x: x + 2.78, y: 1.75, w: 0.35, h: 0.72, align: "center",
        valign: "middle", fontSize: 18, color: AMBER, fontFace: B_FONT, isTextBox: true, margin: 0 });
    }
  });
  const left = [
    ["Matching", "Exact match fires at the watchlist entry's priority. A fuzzy match — confusion-folded or edit-distance 1 — fires one severity lower and is labelled probable, carrying the plate the camera actually read."],
    ["Suppression", "15-minute per-plate-per-camera cooldown, so a parked watchlisted vehicle cannot flood the operator. Alerts are then grouped into episodes: one row per vehicle per camera."],
  ];
  const right = [
    ["Reaction", "An alert boosts the hit camera and its three nearest neighbours to resident ingest slots — coverage tightens around the sighting instead of rotating away from it."],
    ["Correlation", "VAHAN connector returns make, model, class, RTO, insurance status and a masked owner name. SARTHI / eGujCop / AFIS map onto the same connector contract."],
  ];
  [left, right].forEach((col, ci) => {
    col.forEach(([h, b], i) => {
      const x = 0.6 + ci * 6.3;
      const y = 2.85 + i * 1.85;
      panel(s, x, y, 5.9, 1.6);
      s.addText(h, { x: x + 0.32, y: y + 0.22, w: 5.25, h: 0.32, fontSize: 15, bold: true,
        color: AMBER, fontFace: H_FONT, isTextBox: true, margin: 0 });
      s.addText(b, { x: x + 0.32, y: y + 0.6, w: 5.25, h: 0.88, fontSize: 11.5, color: ICE,
        lineSpacing: 16, fontFace: B_FONT, isTextBox: true, margin: 0 });
    });
  });
}

/* ------------------------------------------------------------- 7 test case */
{
  const s = darkSlide("Tracing a designated vehicle", "Evaluation test case");
  panel(s, 0.6, 1.7, 5.75, 4.6);
  s.addText("What the evaluation asks", {
    x: 0.92, y: 1.95, w: 5.1, h: 0.34, fontSize: 15, bold: true, color: AMBER,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText(
    [
      { text: "Onboard ~50 heterogeneous cameras onto one platform.", options: { bullet: true, breakLine: true } },
      { text: "Given a registration number on the day, identify and trace that vehicle across the network.", options: { bullet: true, breakLine: true } },
      { text: "Produce the complete route with timestamped, location-wise movement history.", options: { bullet: true, breakLine: true } },
      { text: "Show continuous watchlist cross-referencing with automated real-time alerts.", options: { bullet: true } },
    ],
    { x: 0.92, y: 2.4, w: 5.1, h: 1.9, fontSize: 12, color: ICE, paraSpaceAfter: 7,
      fontFace: B_FONT, isTextBox: true, margin: 0 }
  );
  s.addText("How SUTRA answers it", {
    x: 0.92, y: 4.45, w: 5.1, h: 0.34, fontSize: 15, bold: true, color: AMBER,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText(
    "Enter the number in Trace. Detections are grouped into per-camera sightings, " +
    "time-ordered and drawn as a GIS polyline with a timeline: every stop carries its " +
    "time window, read confidence, evidence frame and the VAHAN record. A single-camera " +
    "result says so explicitly rather than leaving an unexplained dot.",
    { x: 0.92, y: 4.9, w: 5.1, h: 1.25, fontSize: 12, color: ICE, lineSpacing: 17,
      fontFace: B_FONT, isTextBox: true, margin: 0 }
  );

  panel(s, 6.75, 1.7, 5.95, 4.6);
  s.addText("Live on the hosted instance", {
    x: 7.07, y: 1.95, w: 5.3, h: 0.34, fontSize: 15, bold: true, color: AMBER,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  const stats = [
    ["38", "cameras onboarded across 11 districts and 7 departments"],
    ["1,000+", "plate detections with evidence frames retained"],
    ["59", "distinct vehicles, collapsed from raw reads into one row each"],
    ["94", "watchlist alerts, grouped into operator-facing episodes"],
  ];
  stats.forEach(([big, small], i) => {
    const y = 2.45 + i * 0.88;
    s.addText(big, { x: 7.07, y, w: 1.5, h: 0.45, fontSize: 27, bold: true, color: WHITE,
      valign: "top", fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(small, { x: 8.6, y: y + 0.09, w: 3.85, h: 0.7, fontSize: 11.5, color: ICE,
      lineSpacing: 15, valign: "top", fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  s.addText("Output report exports every detection with UTC and IST timestamps, camera, location and evidence path.", {
    x: 7.07, y: 5.95, w: 5.3, h: 0.5, fontSize: 10.5, italic: true, color: AMBER,
    lineSpacing: 14, valign: "top", fontFace: B_FONT, isTextBox: true, margin: 0,
  });
}

/* -------------------------------------- 8 measured infrastructure (the edge) */
{
  const s = darkSlide("We measured the network before designing for it", "Key innovation");
  s.addText(
    "The sandbox portal rations delivery per client IP. Independent probes at 10 and 20 " +
    "concurrent connections returned the same aggregate — so opening more streams only " +
    "thins each one. This is the constraint a statewide rollout actually faces.",
    { x: 0.6, y: 1.62, w: 12.1, h: 0.62, fontSize: 13, color: ICE, lineSpacing: 19,
      fontFace: B_FONT, isTextBox: true, margin: 0 }
  );
  s.addChart(
    pres.ChartType.bar,
    [{ name: "Aggregate delivered (Mbps)", labels: ["4 streams", "10 streams", "20 streams"], values: [1.5, 5.0, 5.4] }],
    {
      x: 0.6, y: 2.45, w: 6.0, h: 3.5,
      showTitle: true, title: "Portal throughput does not scale with connections",
      titleColor: WHITE, titleFontSize: 12, titleFontFace: B_FONT,
      chartColors: [AMBER], showLegend: false,
      showValue: true, dataLabelPosition: "outEnd", dataLabelColor: WHITE,
      dataLabelFontSize: 11, dataLabelFontFace: B_FONT, dataLabelFormatCode: "0.0",
      catAxisLabelColor: ICE, valAxisLabelColor: MUTE,
      catAxisLabelFontSize: 11, valAxisLabelFontSize: 10,
      catAxisLabelFontFace: B_FONT, valAxisLabelFontFace: B_FONT,
      valGridLine: { color: "24405E", size: 1 }, catGridLine: { style: "none" },
      valAxisMaxVal: 7, plotArea: { fill: { color: INK } },
    }
  );
  const findings = [
    ["~5 Mbps", "hard ceiling per client IP, regardless of connection count"],
    ["48 s", "measured time to first frame — a short dwell window never yields a picture"],
    ["3–4", "streams decodable in real time per IP, at ~1.5 Mbps each"],
  ];
  findings.forEach(([big, small], i) => {
    const y = 2.45 + i * 1.02;
    panel(s, 6.85, y, 5.85, 0.9);
    s.addText(big, { x: 7.12, y: y + 0.16, w: 1.55, h: 0.42, fontSize: 21, bold: true,
      color: AMBER, fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(small, { x: 8.72, y: y + 0.16, w: 3.75, h: 0.6, fontSize: 11.5, color: ICE,
      lineSpacing: 15, fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  panel(s, 6.85, 5.55, 5.85, 1.35, "24405E");
  s.addText("So the scheduler is designed for it", {
    x: 7.12, y: 5.75, w: 5.3, h: 0.3, fontSize: 13.5, bold: true, color: AMBER,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText(
    "A concurrency budget sized to the source, 10-minute dwell rotation with " +
    "least-recently-served fairness, operator pinning and alert-boost. All 30 network " +
    "cameras are covered over time instead of 30 fighting for four sessions at once.",
    { x: 7.12, y: 6.08, w: 5.3, h: 0.72, fontSize: 11, color: ICE, lineSpacing: 15,
      fontFace: B_FONT, isTextBox: true, margin: 0 }
  );
  s.addNotes(
    "This is the differentiator: characterising the infrastructure and designing to it, " +
    "rather than assuming bandwidth and reporting failures as errors."
  );
}

/* --------------------------------------------------------------- 9 security */
{
  const s = darkSlide("Built as a government system", "Cybersecurity & privacy");
  const cols = [
    ["Identity & access", ["JWT with PBKDF2 (200k iterations)", "Signing secret generated per install — never a committed default", "Login rate limiting, failures audited", "RBAC: admin / department-scoped operator / viewer, enforced server-side"]],
    ["Media & data", ["Snapshots, MJPEG, evidence and the alert socket all authenticate", "HttpOnly SameSite cookie — invisible to page scripts, so XSS cannot exfiltrate it", "Evidence confined to its directory, image-type allowlist", "Source URLs restricted to camera protocols — no SSRF, no arbitrary file reads"]],
    ["Accountability", ["Audit trail: logins and failures, onboarding, exports, watchlist edits, acknowledgements", "Security headers, CORS restricted to configured origins", "No continuous central recording — watchlist-match alerting only", "Owner names masked in connector responses"]],
  ];
  cols.forEach(([h, items], i) => {
    const x = 0.6 + i * 4.13;
    panel(s, x, 1.75, 3.85, 2.95);
    disc(s, i + 1, x + 0.28, 1.98);
    s.addText(h, { x: x + 0.85, y: 1.96, w: 2.85, h: 0.36, fontSize: 15, bold: true,
      color: AMBER, fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(
      items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } })),
      { x: x + 0.28, y: 2.45, w: 3.32, h: 2.15, fontSize: 11, color: ICE, paraSpaceAfter: 7,
        valign: "top", fontFace: B_FONT, isTextBox: true, margin: 0 }
    );
  });
  panel(s, 0.6, 4.95, 12.1, 1.95, "24405E");
  s.addText("Verified, not asserted", {
    x: 0.92, y: 5.18, w: 11.5, h: 0.32, fontSize: 15, bold: true, color: AMBER,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText(
    [
      { text: "Ten audit findings were found and closed before submission — a hardcoded signing secret, a fully public evidence store, unauthenticated media endpoints and an open alert socket among them.", options: { bullet: true, breakLine: true } },
      { text: "Each is pinned by an automated test, so a regression fails CI rather than reaching a deployment: 59 tests run on every push alongside a dependency audit and a full-history secret scan.", options: { bullet: true, breakLine: true } },
      { text: "Documented for production: TLS termination, mTLS on federation links, a secrets vault, network segmentation across ingest/analytics/data planes, SIEM export and a hash-chained audit log.", options: { bullet: true } },
    ],
    { x: 0.92, y: 5.55, w: 11.5, h: 1.25, fontSize: 11, color: ICE, paraSpaceAfter: 4,
      valign: "top", fontFace: B_FONT, isTextBox: true, margin: 0 }
  );
}

/* ------------------------------------------------------------ 10 scalability */
{
  const s = darkSlide("Scaling to ~80,000 cameras", "Scalability & cost");
  s.addText("Design principle: video stays at the edge; metadata flows up.", {
    x: 0.6, y: 1.58, w: 12.1, h: 0.32, fontSize: 15, bold: true, color: AMBER,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  panel(s, 0.6, 2.1, 5.75, 2.5, "24405E");
  s.addText("Uplink per camera", {
    x: 0.9, y: 2.28, w: 5.2, h: 0.3, fontSize: 12, bold: true, color: AMBER,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  s.addText("2–6 KB/s", {
    x: 0.9, y: 2.62, w: 2.5, h: 0.5, fontSize: 27, bold: true, color: WHITE,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText("SUTRA — detections and thumbnails", {
    x: 0.9, y: 3.1, w: 2.6, h: 0.5, fontSize: 10.5, color: ICE, lineSpacing: 14,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  s.addText("2–4 Mb/s", {
    x: 3.75, y: 2.62, w: 2.4, h: 0.5, fontSize: 27, bold: true, color: RED,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText("centralised video for the same camera", {
    x: 3.75, y: 3.1, w: 2.4, h: 0.5, fontSize: 10.5, color: ICE, lineSpacing: 14,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  s.addText("≈ 500x", {
    x: 0.9, y: 3.72, w: 1.9, h: 0.45, fontSize: 26, bold: true, color: AMBER,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText("less uplink. A district of 500 cameras federates over ~25 Mb/s; full-video recall stays departmental on existing NVR retention.", {
    x: 2.9, y: 3.72, w: 3.25, h: 0.75, fontSize: 10.5, color: ICE, lineSpacing: 14,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  const tiers = [
    ["Edge · ~150–260 nodes", "Ingest + ANPR on commodity servers. Measured 30–75 ms/frame/core ⇒ 300–500 cameras per 32-core node at 1 fps; ~1,500–2,500 with one T4-class GPU."],
    ["Regional · 6–8", "Kafka event bus, PostgreSQL + PostGIS (partitioned), S3-compatible evidence store — hot 30 d / warm 180 d / cold archive."],
    ["Central", "Federation control plane, registry, search, command centre, government-DB connectors. Kubernetes, HA per tier, DR by cross-region metadata replication."],
  ];
  tiers.forEach(([h, b], i) => {
    const y = 2.1 + i * 1.45;
    panel(s, 6.6, y, 6.1, 1.32);
    s.addText(h, { x: 6.9, y: y + 0.16, w: 5.5, h: 0.3, fontSize: 13.5, bold: true,
      color: WHITE, fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(b, { x: 6.9, y: y + 0.5, w: 5.5, h: 0.72, fontSize: 11, color: ICE,
      lineSpacing: 15, fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  panel(s, 0.6, 4.85, 5.75, 1.9, "24405E");
  s.addText("Indicative capex", {
    x: 0.88, y: 5.05, w: 5.2, h: 0.3, fontSize: 13.5, bold: true, color: AMBER,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  s.addText(
    [
      { text: "Edge-CPU option: ₹40–75 Cr + network", options: { bullet: true, breakLine: true } },
      { text: "GPU option: ₹55–90 Cr, 4x analytics headroom", options: { bullet: true, breakLine: true } },
      { text: "An order of magnitude below centralised-video designs — the state pays for inference, not for hauling video.", options: { bullet: true } },
    ],
    { x: 0.88, y: 5.4, w: 5.2, h: 1.25, fontSize: 11, color: ICE, paraSpaceAfter: 5,
      fontFace: B_FONT, isTextBox: true, margin: 0 }
  );
}

/* --------------------------------------------------- 11 proof it is running */
{
  const s = darkSlide("A deployed system, verified end to end", "Working platform");
  const left = [
    ["Deployment split that mirrors the architecture", "The hosted command centre runs the central tier at 102 MB; ingest and inference run on an edge node at 514 MB for nine cameras. The proposed statewide boundary is the one the demo actually uses."],
    ["Federation proven, not asserted", "The edge pushes cameras, detections, alerts and evidence upstream every 30 seconds, survives restarts, and keeps working when the centre is unreachable."],
  ];
  const right = [
    ["Honest state, everywhere", "Tiles show live, stalled, connecting, unreachable or queued from the ingest workers themselves. A frozen frame is never labelled live; decoder failures are translated into causes an operator can act on."],
    ["Engineering discipline", "CI on every push — tests, build, dependency audit, full-history secret scan — with branch protection and approval-gated production deploys."],
  ];
  [left, right].forEach((col, ci) => {
    col.forEach(([h, b], i) => {
      const x = 0.6 + ci * 6.3;
      const y = 1.75 + i * 2.2;
      panel(s, x, y, 5.9, 1.95);
      disc(s, ci * 2 + i + 1, x + 0.3, y + 0.3);
      s.addText(h, { x: x + 0.93, y: y + 0.26, w: 4.65, h: 0.55, fontSize: 14.5, bold: true,
        color: WHITE, fontFace: H_FONT, isTextBox: true, margin: 0 });
      s.addText(b, { x: x + 0.3, y: y + 0.9, w: 5.3, h: 0.95, fontSize: 11.5, color: ICE,
        lineSpacing: 16, fontFace: B_FONT, isTextBox: true, margin: 0 });
    });
  });
  panel(s, 0.6, 6.2, 12.1, 0.72, "1C3A2A");
  s.addText("17/17 live API endpoints green · 59 automated tests passing · zero duplicate records · real accumulated data from the government feeds", {
    x: 0.6, y: 6.2, w: 12.1, h: 0.72, align: "center", valign: "middle", fontSize: 12.5,
    bold: true, color: GREEN, fontFace: B_FONT, isTextBox: true, margin: 0,
  });
}

/* ------------------------------------------------------- 12 roadmap + close */
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("ROADMAP", {
    x: 0.6, y: 0.5, w: 12.1, h: 0.3, fontSize: 11, bold: true, color: AMBER,
    charSpacing: 2, fontFace: B_FONT, isTextBox: true, margin: 0,
  });
  s.addText("From this platform to statewide", {
    x: 0.6, y: 0.82, w: 12.1, h: 0.7, fontSize: 32, bold: true, color: WHITE,
    fontFace: H_FONT, isTextBox: true, margin: 0,
  });
  const phases = [
    ["Phase 1", "Now", "This platform: registry and GIS, federation middleware, ANPR with temporal voting, watchlist correlation, alerting, trace, RBAC and audit — deployed and verified."],
    ["Phase 2", "Next", "Facial recognition with an AFIS confirmation loop (flagged candidate → human confirmation, never automatic identification), ONVIF auto-discovery, Kafka event bus, PostGIS migration."],
    ["Phase 3", "Scale", "Statewide rollout across the edge/regional/central tiers, eGujCop-fed watchlists, and an onboarding portal for public and private feeds."],
  ];
  phases.forEach(([p, when, body], i) => {
    const y = 1.75 + i * 1.42;
    panel(s, 0.6, y, 12.1, 1.28);
    s.addText(p, { x: 0.92, y: y + 0.2, w: 1.5, h: 0.34, fontSize: 16, bold: true,
      color: AMBER, fontFace: H_FONT, isTextBox: true, margin: 0 });
    s.addText(when, { x: 0.92, y: y + 0.58, w: 1.5, h: 0.28, fontSize: 10.5, color: MUTE,
      charSpacing: 1, fontFace: B_FONT, isTextBox: true, margin: 0 });
    s.addText(body, { x: 2.6, y: y + 0.24, w: 9.8, h: 0.85, fontSize: 12, color: ICE,
      lineSpacing: 17, fontFace: B_FONT, isTextBox: true, margin: 0 });
  });
  panel(s, 0.6, 6.1, 12.1, 0.95, "24405E");
  s.addText("SUTRA", {
    x: 0.95, y: 6.28, w: 2.1, h: 0.5, fontSize: 24, bold: true, color: WHITE,
    fontFace: H_FONT, charSpacing: 3, isTextBox: true, margin: 0,
  });
  s.addText("Statewide Unified Tracking, Registry & Analytics  ·  github.com/laveshparyani/SUTRA  ·  open-source throughout", {
    x: 3.2, y: 6.35, w: 9.2, h: 0.45, valign: "middle", fontSize: 12, color: ICE,
    fontFace: B_FONT, isTextBox: true, margin: 0,
  });
}

pres.writeFile({ fileName: "submission/SUTRA_Solution_Presentation.pptx" })
  .then((f) => console.log("wrote", f));
