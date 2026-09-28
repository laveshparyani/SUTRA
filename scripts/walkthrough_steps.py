"""The walkthrough's script: one entry per test case from docs/TESTING.md.

Kept apart from the recorder so the narration can be synthesised without a
browser, and so the running order is readable in one place.

Each step is (ref, title, narration, action). `action` is called with a helper
that owns the page, the annotations and the clock; it returns a verdict string
when the check passes and raises when it does not — the recorder catches that,
marks the step as an issue on screen, writes it to the defect report and
carries on to the next test rather than abandoning the take.
"""

REF_INTRO = "intro"


def steps():
    """Returns the ordered walkthrough. Imported by both the narrator and the recorder."""
    return [

        # ------------------------------------------------------------ opening
        (REF_INTRO, "SUTRA — verification walkthrough",
         "This is a verification walkthrough of SUTRA, the platform submitted for the "
         "Gujarat Police CCTV Integration Challenge. Rather than a highlights reel, this "
         "runs the acceptance tests in the submitted test plan, one at a time, against the "
         "live system. Each check names the requirement it proves, and the result is shown "
         "on screen as it happens.",
         "intro"),

        # ------------------------------------------------- 1. Model 1 registry
        ("1.1", "Registry holds real camera metadata",
         "Model One is the mandatory foundation: a central registry of every camera. The "
         "registry holds thirty eight cameras across seven departments, each with its "
         "location, district, protocol and live health — not placeholders.",
         "reg_metadata"),

        ("1.2", "API-based onboarding from the portal catalogue",
         "Onboarding is automatic. Discover reads the challenge portal's own catalogue and "
         "updates all thirty government cameras in place, keeping their history rather than "
         "creating duplicates.",
         "reg_discover"),

        ("1.3", "Search and filtering",
         "The registry is searchable and filterable by department, so an operator can narrow "
         "eighty thousand cameras to the ones they need.",
         "reg_filter"),

        ("1.4", "CSV export",
         "The whole registry exports to CSV — one row per camera with its full metadata, "
         "which is what a department needs for its own asset records.",
         "reg_export"),

        ("1.5", "GIS coverage map with layers",
         "The Atlas map is the GIS half of Model One. It layers by department, camera type "
         "and status, with an optional coverage radius coloured by health, so a dead camera's "
         "zone reads as a gap rather than as cover.",
         "atlas_map"),

        ("1.6", "Honest per-camera health",
         "Camera health is reported honestly. Tiles read live, stalled, connecting, "
         "unreachable, queued or not pooled — and a tile that is not streaming says why. "
         "A frozen frame is never labelled live.",
         "wall_states"),

        ("1.7", "District gap analysis",
         "Gap analysis reports coverage by district, flagging thin coverage and ageing "
         "infrastructure — the planning output Model One exists to produce.",
         "atlas_gap"),

        ("1.8", "Metadata audit trail",
         "Every action against the registry is audited. The discovery and export just "
         "performed appear here, attributed to the signed-in user with a timestamp.",
         "atlas_audit"),

        # ------------------------------------------- 2. Model 3 federation
        ("2.1", "Heterogeneous sources, one platform",
         "Model Three federates heterogeneous sources. Government cameras arrive over "
         "authenticated R T S P while recorded file sources run alongside them, both reaching "
         "the same pipeline through one adapter contract.",
         "fed_sources"),

        ("2.2", "Credentials are never stored with the camera",
         "The portal authenticates every connection, and the stored source URL carries no "
         "email and no password. Credentials are injected at connection time and never "
         "written to the registry, the export, or the logs.",
         "fed_credentials"),

        ("2.3", "Government-database correlation",
         "Detections are correlated against a government vehicle database through a VAHAN "
         "shaped connector — make, model, class, registering office and insurance status, "
         "with the owner name masked.",
         "fed_vahan"),

        # ------------------------------------------------- 3. AI analytics
        ("3.1", "ANPR on the live government feeds",
         "Number plate recognition runs continuously on the government feeds. These reads "
         "carry the camera they came from, a timestamp, and the confidence of each read.",
         "anpr_live"),

        ("3.2", "Records collapse by vehicle",
         "The same vehicle read many times is one vehicle, not many rows. Raw reads collapse "
         "into sightings, and sightings into vehicles, so an operator sees vehicles rather "
         "than noise.",
         "anpr_grouping"),

        ("3.3", "Every read carries its evidence",
         "Every read keeps the crop the recognition ran on, so any plate can be checked by a "
         "human. That is the minimum bar for anything supporting an investigation.",
         "anpr_evidence"),

        ("3.4", "Confidence is published, not hidden",
         "Confidence is published with every read. These are plates fifty to ninety pixels "
         "tall on a live street. Reads above about zero point nine five are reliable; below "
         "that characters can be wrong, and the column lets a reader apply their own "
         "threshold instead of trusting all of them equally.",
         "anpr_confidence"),

        ("3.5", "Scene analytics beyond plates",
         "Beyond plates, every camera gets person and vehicle counts from an object detection "
         "sidecar — all on C P U, with no G P U anywhere in this deployment.",
         "scene_counts"),

        # ------------------------------------------ 4. Watchlist and alerting
        ("4.1", "Watchlist database",
         "The watchlist holds stolen and suspect vehicles, each with an F I R reference and a "
         "priority, mapping one to one onto e-Guj-Cop records in production.",
         "watch_list"),

        ("4.2", "Adding an entry is audited",
         "Adding a vehicle takes effect immediately and is recorded in the audit trail against "
         "the user who added it.",
         "watch_add"),

        ("4.3", "Automated alerts with evidence",
         "When a read matches the watchlist, an alert fires automatically carrying the camera, "
         "the location, the time, and an annotated evidence frame.",
         "alert_list"),

        ("4.4", "Alerts group into episodes",
         "A watchlisted vehicle parked in one camera's view would otherwise fire endlessly. "
         "Alerts group into episodes — one row per vehicle per camera, with a hit count and "
         "how many remain unacknowledged.",
         "alert_episodes"),

        ("4.5", "Fuzzy matches are labelled as fuzzy",
         "Where a match was fuzzy rather than exact, it is labelled a probable match and shows "
         "the characters the camera actually read. An operator is never handed a one character "
         "inference as a confirmed identification.",
         "alert_probable"),

        ("4.6", "Acknowledgement workflow",
         "Alerts are acknowledged by an operator, and the acknowledgement is audited.",
         "alert_ack"),

        # --------------------------------------------- 5. The evaluation case
        ("5.1", "Trace a designated vehicle",
         "This is the evaluation scenario. Given a registration number, the platform returns "
         "that vehicle's history across the integrated network.",
         "trace_search"),

        ("5.2", "Timestamped, location-wise movement history",
         "The result is a timestamped, location-wise movement history: each sighting with its "
         "camera, district, time window, read confidence and evidence image.",
         "trace_timeline"),

        ("5.3", "Route on the GIS map",
         "Sightings are plotted on the GIS map in sequence. Where a vehicle has been seen at "
         "one location only, the platform says so plainly rather than leaving an unexplained "
         "point — a route line is drawn as soon as a second camera reads the same plate.",
         "trace_map"),

        ("5.4", "An unknown plate fails cleanly",
         "A registration number the network has never seen returns a clear not-sighted result, "
         "not an error and not an empty screen.",
         "trace_unknown"),

        # ------------------------------------------------- 6. Output report
        ("6.1", "Output report export",
         "The required output report exports directly from the platform: detected plates with "
         "their camera, location, confidence, and both U T C and I S T timestamps.",
         "report_export"),

        # ----------------------------------------------------- 7. Security
        ("7.1", "No anonymous access to the API",
         "Security is enforced server side. Requesting camera data without a session returns "
         "unauthorised rather than data.",
         "sec_anon"),

        ("7.2", "Role-based access control",
         "Roles are enforced, not merely displayed. Signed in as a read-only viewer, the "
         "actions that change state are gone from the interface and refused by the server.",
         "sec_rbac"),

        # -------------------------------------------------------- closing
        ("close", "Verification complete",
         "That is the acceptance test plan run end to end against the live platform. The "
         "hosted instance, the source code, the output report and this test plan are all "
         "linked in the submission.",
         "closing"),
    ]
