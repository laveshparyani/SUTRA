export function PlateChip({ plate, commercial = false }) {
  if (!plate) return <span className="dim">—</span>;
  return <span className={`plate${commercial ? " commercial" : ""}`}>{plate}</span>;
}
