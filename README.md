# Immich Photos — Home Assistant Integration

A feature-rich Home Assistant custom integration for [Immich](https://immich.app), heavily inspired by [ha-google-photos](https://github.com/Daanoz/ha-google-photos).

## Features

- 📸 **Camera entities** for each album — display photos directly on your dashboards
- 🔀 **Random selection** from a large pool using Immich's `searchRandom` API
- 🗓️ **Date filtering** — show only photos after/before a date, this month, this year, or a custom range
- 🖼️ **Combine Images mode** — automatically merges two portrait photos side-by-side into a landscape frame (same as ha-google-photos)
- ✂️ **Crop modes** — Original (letterboxed), Crop (fill), or Combine Images
- ⏱️ **Configurable update interval** — from 1 minute to 1 hour
- 🏷️ **Sensor entities** — filename, creation timestamp, photo count
- 🎛️ **Select entities** — change crop mode, selection mode, update interval, and date filter live from the UI
- 🔧 **Services** — `next_media`, `next_media_all`, `set_date_filter` for use in automations

---

## Installation

### Via HACS (recommended)

1. In HACS, go to **Integrations → Custom repositories**
2. Add: `https://github.com/Seekersdk/HA-Immich` as type **Integration**
3. Find **Immich Photos** and click **Install**
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/immich_photos` folder into your HA config's `custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Immich Photos**
3. Enter your Immich URL and API key
   - API key: Immich web → Account Settings → API Keys → New API Key
4. Select which albums to expose (Favorites, All Photos, or any of your albums)

To add/change albums later, click **Configure** on the integration card.

---

## Entities created per album

| Platform | Name | Description |
|---|---|---|
| `camera` | `{Album} Media` | Current photo — use in picture-entity or picture cards |
| `sensor` | `{Album} Filename` | Filename of the current photo |
| `sensor` | `{Album} Creation Timestamp` | Timestamp the photo was taken |
| `sensor` | `{Album} Media Count` | Number of photos in the pool |
| `select` | `{Album} Image Selection Mode` | Random or Album order |
| `select` | `{Album} Crop Mode` | Original / Crop / Combine images |
| `select` | `{Album} Update Interval` | How often to auto-advance |
| `select` | `{Album} Date Filter` | Date filtering mode |

---

## Crop Modes

### Original
Photo is scaled to fit the card's dimensions, preserving aspect ratio (letterboxed). Best for preserving composition.

### Crop
Photo is center-cropped to fill the target size exactly. No letterboxing, but edges may be cut off.

### Combine Images ⭐
This is the killer feature. When the current photo is **portrait** (taller than wide), the integration automatically fetches a *second* portrait photo from the pool and places both **side by side** in a single landscape image.

This results in much less wasted canvas space compared to cropping a single portrait to landscape — exactly the same smart behavior as the ha-google-photos integration.

```
┌─────────┬─────────┐
│         │         │
│ Photo 1 │ Photo 2 │  ← Two portraits → one landscape frame
│         │         │
└─────────┴─────────┘
```

---

## Date Filtering

You can filter which photos appear in the pool using the **Date Filter** select entity or the `set_date_filter` service:

| Mode | Description |
|---|---|
| `None` | All photos (no filter) |
| `After date` | Photos taken after a specific date |
| `Before date` | Photos taken before a specific date |
| `Between dates` | Photos taken within a date range |
| `This month` | Only photos from the current calendar month |
| `This year` | Only photos from the current calendar year |

When you change the filter, the photo pool is automatically refreshed from Immich.

---

## Services

### `immich_photos.next_media`
Advance to the next photo on specific camera entities.

```yaml
service: immich_photos.next_media
data:
  entity_id: camera.immich_favorites_media
  mode: Random   # or "Album order"
```

### `immich_photos.next_media_all`
Advance all Immich camera entities at once.

```yaml
service: immich_photos.next_media_all
data:
  mode: Random
```

### `immich_photos.set_date_filter`
Dynamically change the date filter (great for automations).

```yaml
# Show only photos from this summer
service: immich_photos.set_date_filter
data:
  filter_mode: "Between dates"
  after: "2024-06-01"
  before: "2024-08-31"

# Show only this month's photos
service: immich_photos.set_date_filter
data:
  filter_mode: "This month"

# Remove all filters
service: immich_photos.set_date_filter
data:
  filter_mode: "None"
```

---

## Dashboard Examples

### Picture Entity Card
```yaml
type: picture-entity
entity: camera.immich_favorites_media
show_state: false
show_name: false
aspect_ratio: "16:9"
camera_view: auto
tap_action:
  action: call-service
  service: immich_photos.next_media
  data:
    entity_id: camera.immich_favorites_media
    mode: Random
```

### Lovelace Wallpanel (screensaver)
Works great with [lovelace-wallpanel](https://github.com/j-a-n/lovelace-wallpanel):

```yaml
wallpanel:
  enabled: true
  hide_toolbar: true
  hide_sidebar: true
  fullscreen: true
  image_fit: cover
  image_url: media-entity://camera.immich_favorites_media
```

Set **Crop Mode** to `Combine images` and `image_fit: cover` for best results.

### Automation: advance photo every 10 minutes
```yaml
alias: Immich photo frame advance
trigger:
  - platform: time_pattern
    minutes: "/10"
action:
  - service: immich_photos.next_media
    data:
      entity_id: camera.immich_favorites_media
      mode: Random
```

### Automation: show this year's photos on New Year's Day
```yaml
alias: New Year photo memories
trigger:
  - platform: time
    at: "00:00:00"
    day: 1
    month: 1
action:
  - service: immich_photos.set_date_filter
    data:
      filter_mode: "This year"
```

---

## Debugging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.immich_photos: debug
```

---

## How It Works

1. On startup, the integration calls `POST /api/search/metadata` (paginated) to build a local **asset pool** for each album. This pool is cached for **3 hours**.
2. On each update interval tick (default 5 min), it picks the next image from the pool using either **Random** or **Album order** mode.
3. If **Combine Images** mode is active and the selected photo is portrait, a second portrait photo is picked from the pool and both are composited side-by-side using Pillow.
4. The resulting JPEG is served to HA's camera platform and displayed on dashboards.
5. Date filters use Immich's `takenAfter` / `takenBefore` API parameters — only matching assets enter the pool.

---

## Requirements

- Home Assistant 2023.x or newer
- Immich 1.90+ (needs `POST /api/search/random` and `POST /api/search/metadata`)
- Python package: `Pillow>=10.0.0` (auto-installed)
