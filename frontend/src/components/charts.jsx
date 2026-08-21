/**
 * Chart primitives — inline SVG, no charting dependency.
 *
 * Colours come from the validated palette in styles.css (`--series-*` and the
 * reserved `--status-*` roles). Categorical hues are assigned in fixed slot
 * order and never cycled; status colours are never reused as a series.
 *
 * Every chart ships a hover layer, recessive axes, and a table fallback via
 * title/aria text so identity is never carried by colour alone.
 */

import { useState } from "react";

const SERIES = [
  "var(--series-1)", "var(--series-2)", "var(--series-3)",
  "var(--series-4)", "var(--series-5)", "var(--series-6)",
];

export const seriesColor = (i) => SERIES[i % SERIES.length];

const fmt = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

/* ------------------------------------------------------------------ shell */

export function ChartCard({ title, subtitle, hint, children, actions, wide = false }) {
  return (
    <figure className={`chart-card${wide ? " wide" : ""}`}>
      <figcaption className="chart-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions}
      </figcaption>
      <div className="chart-body">{children}</div>
      {hint && <p className="chart-hint">{hint}</p>}
    </figure>
  );
}

/* --------------------------------------------------- change over time: area */

export function AreaChart({ data, height = 132, valueKey = "count", labelKey = "label" }) {
  const [hover, setHover] = useState(null);
  if (!data?.length) return <Empty text="No activity in this window" />;

  const W = 560, H = height, PAD_L = 34, PAD_B = 20, PAD_T = 8;
  const max = Math.max(...data.map((d) => d[valueKey]), 1);
  const iw = W - PAD_L - 8, ih = H - PAD_B - PAD_T;
  const x = (i) => PAD_L + (data.length === 1 ? iw / 2 : (i / (data.length - 1)) * iw);
  const y = (v) => PAD_T + ih - (v / max) * ih;

  const line = data.map((d, i) => `${i ? "L" : "M"}${x(i)},${y(d[valueKey])}`).join(" ");
  const area = `${line} L${x(data.length - 1)},${PAD_T + ih} L${x(0)},${PAD_T + ih} Z`;
  const ticks = [0, Math.round(max / 2), max];

  return (
    <div className="chart-plot">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`Detections per hour. Peak ${max}.`}
        onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD_L} x2={W - 8} y1={y(t)} y2={y(t)} className="grid" />
            <text x={PAD_L - 6} y={y(t) + 3.5} className="axis-label" textAnchor="end">{fmt(t)}</text>
          </g>
        ))}
        <defs>
          <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--series-1)" stopOpacity="0.34" />
            <stop offset="100%" stopColor="var(--series-1)" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#areaFill)" />
        <path d={line} fill="none" stroke="var(--series-1)" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" />

        {/* hover: crosshair + marker */}
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PAD_T} y2={PAD_T + ih} className="crosshair" />
            <circle cx={x(hover)} cy={y(data[hover][valueKey])} r="4.5"
              fill="var(--series-1)" stroke="var(--bg-1)" strokeWidth="2" />
          </g>
        )}
        {data.map((d, i) => (
          <rect key={i} x={x(i) - iw / data.length / 2} y={PAD_T}
            width={Math.max(iw / data.length, 6)} height={ih}
            fill="transparent" onMouseEnter={() => setHover(i)} />
        ))}

        {data.map((d, i) =>
          i % Math.ceil(data.length / 6) === 0 ? (
            <text key={i} x={x(i)} y={H - 5} className="axis-label" textAnchor="middle">
              {d[labelKey]}
            </text>
          ) : null
        )}
      </svg>
      {hover !== null && (
        <div className="chart-tip" style={{ left: `${(x(hover) / W) * 100}%` }}>
          <b>{data[hover][valueKey]}</b> detections
          <span>{data[hover][labelKey]}</span>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------ magnitude: horizontal bars */

export function BarList({ data, labelKey, valueKey, unit = "", colorBy = "single", max: maxProp }) {
  if (!data?.length) return <Empty text="Nothing recorded yet" />;
  const max = maxProp ?? Math.max(...data.map((d) => d[valueKey]), 1);

  return (
    <ul className="bar-list">
      {data.map((d, i) => {
        const pct = (d[valueKey] / max) * 100;
        const color = colorBy === "series" ? seriesColor(i) : "var(--series-1)";
        return (
          <li key={i} title={`${d[labelKey]}: ${d[valueKey]}${unit}`}>
            <span className="bar-label">{d[labelKey]}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${Math.max(pct, 1.5)}%`, background: color }} />
            </span>
            <span className="bar-value mono">{fmt(d[valueKey])}{unit}</span>
          </li>
        );
      })}
    </ul>
  );
}

/* ------------------------------------------------------- state: status donut */

const STATUS_COLOR = {
  ok: "var(--status-good)",
  healthy: "var(--status-good)",
  connecting: "var(--status-warning)",
  degraded: "var(--status-serious)",
  down: "var(--status-critical)",
  unknown: "var(--text-2)",
};

export function StatusDonut({ data, labelKey = "state", valueKey = "count", centerLabel }) {
  const [hover, setHover] = useState(null);
  const total = data?.reduce((s, d) => s + d[valueKey], 0) ?? 0;
  if (!total) return <Empty text="No cameras registered" />;

  const R = 52, SW = 15, C = 2 * Math.PI * R;
  let offset = 0;

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 130 130" className="donut" role="img"
        aria-label={data.map((d) => `${d[labelKey]}: ${d[valueKey]}`).join(", ")}>
        <g transform="translate(65,65) rotate(-90)">
          {data.map((d, i) => {
            const frac = d[valueKey] / total;
            // 2px surface gap between adjacent segments
            const len = Math.max(frac * C - 2, 1);
            const seg = (
              <circle key={i} r={R} fill="none" strokeWidth={hover === i ? SW + 3 : SW}
                stroke={STATUS_COLOR[d[labelKey]] ?? "var(--text-2)"}
                strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-offset}
                onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                style={{ transition: "stroke-width .12s" }} />
            );
            offset += frac * C;
            return seg;
          })}
        </g>
        <text x="65" y="61" className="donut-total" textAnchor="middle">{total}</text>
        <text x="65" y="76" className="donut-sub" textAnchor="middle">{centerLabel}</text>
      </svg>
      <ul className="legend">
        {data.map((d, i) => (
          <li key={i} className={hover === i ? "on" : ""}
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <i style={{ background: STATUS_COLOR[d[labelKey]] ?? "var(--text-2)" }} />
            <span>{d[labelKey]}</span>
            <b className="mono">{d[valueKey]}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* --------------------------------------------- ordered magnitude: band chart */

export function BandChart({ data, labelKey = "band", valueKey = "count" }) {
  const total = data?.reduce((s, d) => s + d[valueKey], 0) ?? 0;
  if (!total) return <Empty text="No reads yet" />;
  // sequential single hue, light -> dark, matching the ordered bands
  const ramp = ["var(--seq-1)", "var(--seq-2)", "var(--seq-3)", "var(--seq-4)"];

  return (
    <div className="band-chart">
      <div className="band-bar">
        {data.map((d, i) =>
          d[valueKey] ? (
            <span key={i} style={{ flexGrow: d[valueKey], background: ramp[i % ramp.length] }}
              title={`${d[labelKey]}: ${d[valueKey]} reads (${Math.round((d[valueKey] / total) * 100)}%)`} />
          ) : null
        )}
      </div>
      <ul className="legend wrap">
        {data.map((d, i) => (
          <li key={i}>
            <i style={{ background: ramp[i % ramp.length] }} />
            <span>{d[labelKey]}</span>
            <b className="mono">{d[valueKey]}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------- stat tile */

export function StatTile({ label, value, hint, tone = "default", spark }) {
  return (
    <div className={`stat-tile ${tone}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value ?? "—"}</div>
      {hint && <div className="stat-hint">{hint}</div>}
      {spark?.length > 1 && <Sparkline data={spark} />}
    </div>
  );
}

function Sparkline({ data }) {
  const max = Math.max(...data, 1);
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * 100},${18 - (v / max) * 16}`).join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 100 20" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.6"
        vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

function Empty({ text }) {
  return <div className="chart-empty">{text}</div>;
}
