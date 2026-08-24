# TREES under BUS

**Pick the seat the sun won't find.**

TREES under BUS looks at your actual road trip — the real route, the real
road headings, and the real position of the sun at every point along the
way — and tells you whether to sit on the **left** or the **right** side of
the bus/car/train.

This document explains what the app does, the math behind it, and how
mapping, search, and routing are wired in.

---

## 1. What it does, in one paragraph

You give it a starting point, a destination, a departure date/time, and a
mode of travel. It fetches one or more real driving routes between the two
points, breaks each route into small segments, and for every segment it
works out two things: which compass direction the vehicle is heading, and
where the sun is in the sky at the time the vehicle would be passing through
that segment. Comparing those two angles tells it whether the sun would be
shining through the left window, the right window, or neither. It adds up
the minutes for each side across the whole route and tells you which side
gets less sun.

---

## 2. Step-by-step flow

1. **Places** — you type or pick (via search, GPS, or tapping the full-screen
   map) a "From" and a "To" location.
2. **Date & time, and mode** — when you're leaving, and whether it's a bus,
   car, or train.
3. **Routing** — the app asks a routing service for one or more real road
   routes between the two points.
4. **Per-segment analysis** — every stretch of road on the route is scored
   for sun exposure (see §3 below).
5. **Recommendation** — the app totals up "left minutes" vs. "right minutes"
   and tells you which side to sit on, with a seat diagram for 2‑seater /
   3‑seater bus layouts.

---

## 3. The core calculation

This is the part that actually answers "which side is sunny," broken into
four pieces: **heading**, **sun position**, **relative bearing**, and
**classification**.

### 3.1 Vehicle heading (bearing)

For every pair of consecutive points on the route polyline, the app
computes the **initial bearing** — the compass direction (0–360°, where 0°
= north, 90° = east) you'd be facing if you drove in a straight line from
the first point to the second. This uses the standard great-circle bearing
formula:

```
θ = atan2( sin(Δlon)·cos(lat2),
           cos(lat1)·sin(lat2) − sin(lat1)·cos(lat2)·cos(Δlon) )
```

This is recomputed for every segment, so a winding road correctly produces
a heading that changes segment by segment — it's not just "the direction
from origin to destination."

### 3.2 Sun position (azimuth & elevation)

For each segment, the app estimates the clock time the vehicle would reach
that segment (see §3.3), then computes where the sun is in the sky **at
that moment, at that segment's coordinates**, using a low-precision solar
position algorithm (a simplified NOAA/Meeus-style formula). It returns two
angles:

- **Azimuth** — the compass direction of the sun (0–360°, same convention
  as heading above).
- **Elevation** — how high the sun is above the horizon. Negative means
  it's below the horizon (night).

The algorithm accounts for the date (day of year, via Julian date), the
time of day, and the segment's latitude/longitude. It's accurate to well
under a degree — far more precision than a "which side of the bus"
question needs.

### 3.3 Timing along the route

The routing service returns a total trip duration. The app distributes that
duration across segments in proportion to each segment's share of the total
distance (i.e., it assumes a roughly constant average speed — it does not
account for traffic, stops, or slow sections separately). The timestamp for
each segment is `departure time + cumulative time to reach that segment's
midpoint`.

### 3.4 Relative bearing → side of the vehicle

Once a segment has both a heading and a sun azimuth, the app computes the
**relative bearing**:

```
relativeBearing = normalize(sunAzimuth − vehicleHeading)   // −180° … +180°
```

- `0°` means the sun is dead ahead.
- `±180°` means the sun is directly behind.
- `+90°` means the sun is directly off the **right** side (positive =
  right, since compass angles increase clockwise).
- `−90°` means the sun is directly off the **left** side.

### 3.5 Classifying "sunny," "not sunny," and how strong

Two extra rules keep the recommendation realistic:

- **Below the horizon → no sun.** If elevation ≤ 0°, the segment is marked
  "none" regardless of bearing.
- **Dead-ahead / dead-behind → no meaningful side exposure.** Sun that's
  nearly in front of or behind the vehicle doesn't come through a *side*
  window in any useful way, even though the raw bearing math would call it
  a small angle. The app defines a "deadzone" — a window around 0°/180° —
  and anything inside it is classified as "none." The deadzone width is
  controlled by your **sun tolerance** setting: "I run hot" uses a
  narrower deadzone (flags sun sooner), "I don't mind a little sun" uses a
  wider one.
- **Weighting by how direct the sun is.** Sun hitting the window at a sharp
  grazing angle is far less bothersome than sun coming in perpendicular to
  the window. Each segment gets a weight of `sin(|relativeBearing|)`, which
  peaks at 1.0 when the sun is exactly perpendicular (90° off the side) and
  fades toward 0 near dead-ahead/behind. This weight isn't used to override
  the left/right total, but it's the basis for a more nuanced "how bad is
  it" score than raw minutes alone.

### 3.6 Aggregating into a recommendation

Every segment now has a `side` (`left` / `right` / `none`) and a duration.
The app sums the durations per side across the whole route, and:

- If both totals are near zero → **"No significant sun on this trip."**
- If the two totals are close (within about a minute) → **"Either side
  works."**
- Otherwise → **"Sit on the [side with fewer sun-minutes]."**

Consecutive segments with the same classification are merged into "runs" —
this is what lets the app describe a trip as, e.g., "the sunny side changes
3 times along this route," for winding roads that face different
directions at different points.

### 3.7 Seat layout (2-seater vs. 3-seater)

Many buses have an asymmetric layout — two seats on one side of the aisle,
three on the other. Since "which side" only matters if you know which side
you're picking, the app lets you flag which side is the 2-seater, and
re-labels the recommendation accordingly (e.g., "sit on the left (2-seater
· Left)").

### 3.8 Orientation convention

**Left and right are always defined as if you're a passenger facing the
front of the vehicle, in the direction of travel** — i.e., facing forward
toward the driver. If your seat faces backward, the physical sides you'd
want are swapped.

---

## 4. How maps and location data are used

The app doesn't have its own map or address database. It's built entirely
on open, publicly available services, wired together in the browser:

| Purpose | Service | What it's used for |
|---|---|---|
| Base map tiles | **OpenStreetMap** tile servers, rendered via **Leaflet.js** | The visual map background, both in the route-detail view and the full-screen location picker. |
| Search-as-you-type / address lookup | **Nominatim** (OpenStreetMap's geocoding API) | Turning typed text ("Gandhipuram") into coordinates, and turning coordinates back into a readable address (reverse geocoding) when you drop a pin or use GPS. |
| Nearby bus stand search | **Nominatim**, biased to the currently visible map area | Powers the "🚌 Find bus stands nearby" button inside the map picker — it searches for `bus stand` within the map's current viewport bounds. |
| Route geometry & timing | **OSRM** (Open Source Routing Machine, public driving-routes API) | Returns the actual road-following polyline between origin and destination, alternative routes, total distance, and total duration — this is what gets fed into the segment/bearing/sun-position pipeline above. |

### 4.1 Picking a location

There are three ways to set "From" or "To":

1. **Type and pick from suggestions** — as you type, the app queries
   Nominatim (biased first toward Tamil Nadu, then falling back to a
   worldwide search) and shows matching places.
2. **Full-screen map picker** — tap "📍 Pick on map." This opens the map
   full-screen. You can search inside it, tap anywhere to drop a pin, drag
   the pin to fine-tune it, or use "Find bus stands nearby" to see bus
   stands in the currently visible area. Confirming reverse-geocodes the
   pin into a readable address and fills the field.
3. **Use my location** — uses the browser's GPS (`navigator.geolocation`),
   then reverse-geocodes the coordinates into an address.

None of these three methods depend on each other — you can plan a trip
between two places you're not currently at and never touch GPS at all.

### 4.2 Why search or GPS might not work in some viewers

Some embedded/preview browser windows (for example, an in-chat file
preview) apply their own permissions policy that blocks GPS and/or outbound
network requests, independent of anything in this app's code. If search
suggestions or "Use my location" don't respond, download the HTML file and
open it directly in a normal browser tab — outside that kind of sandboxed
preview, both work normally.

---

## 5. Data model (for anyone reading the code)

```
Route     { geometry, distance, duration, segments, runs, aggregate }
Segment   { start, end, distance, durationSec, bearing, timestamp,
            sunAzimuth, sunElevation, relBearing, side, weight }
Run       { side, durationSec, startOffsetSec, coords }
Aggregate { left, right, none, leftScore, rightScore, total }
```

- **Route** — one option returned by the routing service, plus everything
  derived from it.
- **Segment** — one small piece of road between two consecutive polyline
  points, with its own heading, timestamp, and sun classification.
- **Run** — consecutive segments with the same `side` merged together (used
  for the "changes N times" summary).
- **Aggregate** — the route-level totals used to produce the final
  recommendation.

---

## 6. Known limitations

- **Weather isn't modeled.** The calculation is purely geometric (where the
  sun *would* be); clouds, haze, and overcast skies aren't accounted for.
- **Terrain and buildings aren't modeled.** A mountain, tall building, or
  even a stand of trees can block sun that the geometry says should be
  present.
- **Even pacing assumption.** Time is distributed across the route in
  proportion to distance, not based on real-time traffic, stops, or speed
  limits per road segment.
- **Time zone.** Departure time is read in your device's current time
  zone, not necessarily the origin's local time zone (relevant mainly for
  long-distance or cross-time-zone trips).
- **Public demo services.** Nominatim and OSRM are free public services
  without an API key, provided as a courtesy by OpenStreetMap volunteers.
  They can be slower or rate-limited compared to a paid commercial API.

---

## 7. Feedback

There's a **"📝 Post a review"** button fixed in the corner of every screen
in the app — it links to a short feedback form. Bug reports, confusing UI,
or "this recommendation didn't match what actually happened" reports are
all useful there.
