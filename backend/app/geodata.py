"""Approximate coordinates for known feed locations.

The hackathon portal exposes location names only — no coordinates. These are
city/landmark-level approximations so cameras render on the GIS map. Every
camera seeded from here is flagged `coords_approx=True`; operators can correct
positions via the Atlas API/UI. Departments are inferred from location context
(the dataset spans Health, Police, GSRTC, Panchayat, Municipal).
"""

# keyword (lower-case, matched against location string) -> (lat, lon, district, department)
LOCATION_HINTS: list[tuple[str, tuple[float, float, str, str]]] = [
    ("chiman", (23.0455, 72.5310, "Ahmedabad", "Municipal")),
    ("janpath", (23.0330, 72.5610, "Ahmedabad", "Municipal")),
    ("o.n.g.c", (23.0480, 72.5290, "Ahmedabad", "Police")),
    ("paldi", (23.0117, 72.5624, "Ahmedabad", "Police")),
    ("visat", (23.1110, 72.5850, "Gandhinagar", "Police")),
    ("timbavadi", (21.4890, 70.4580, "Junagadh", "Municipal")),
    ("gir-somnath", (20.9160, 70.3670, "Gir Somnath", "Police")),
    ("majewadi", (21.5290, 70.4640, "Junagadh", "Municipal")),
    ("junagadh", (21.5222, 70.4579, "Junagadh", "Municipal")),
    ("adalaj", (23.1640, 72.5810, "Gandhinagar", "GSRTC")),
    ("cn vidhyalaya", (23.0210, 72.5570, "Ahmedabad", "Municipal")),
    ("delight", (23.0270, 72.5870, "Ahmedabad", "Municipal")),
    ("suvidha", (23.0060, 72.5250, "Ahmedabad", "Municipal")),
    ("rajkot", (22.3039, 70.8022, "Rajkot", "Police")),
    ("khaparia", (20.8120, 72.9860, "Navsari", "Panchayat")),
    ("mohanpura", (22.7750, 71.6480, "Surendranagar", "Panchayat")),
    ("patan", (23.8500, 72.1250, "Patan", "Police")),
    ("mervada", (23.8420, 72.1100, "Patan", "Panchayat")),
    ("kheram", (23.8300, 72.1400, "Patan", "Panchayat")),
    ("dehgam", (23.1690, 72.8210, "Gandhinagar", "Panchayat")),
    ("dhanori", (23.1500, 72.8500, "Gandhinagar", "Panchayat")),
    ("tankal", (20.7700, 72.9700, "Navsari", "Panchayat")),
    ("bilimora", (20.7690, 72.9610, "Navsari", "Municipal")),
    ("gandhidham", (23.0753, 70.1337, "Kutch", "Municipal")),
]

_FALLBACK = (22.2587, 71.1924, "", "Unassigned")  # Gujarat centroid


def locate(location: str) -> tuple[float, float, str, str]:
    """Return (lat, lon, district, department) for a location string."""
    loc = location.lower()
    for keyword, hit in LOCATION_HINTS:
        if keyword in loc:
            return hit
    return _FALLBACK
