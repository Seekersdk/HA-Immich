# Immich Photos — Home Assistant Integration

A Home Assistant custom integration for [Immich](https://immich.app) that displays photos from your albums on dashboards and digital photo frames.

Built on top of [outadoc/immich-home-assistant](https://github.com/outadoc/immich-home-assistant) with additional features for photo frame use cases.

---

## Features

- **Camera entities** per album — show photos directly in picture cards and Lovelace dashboards
- **Random or album-order selection** from a cached asset pool
- **Combine Images mode** — automatically places two portrait photos above and below each other in a portrait frame
- **Crop modes** — Original (letterboxed), Crop (fill), or Combine Images
- **Configurable update interval** — from 1 minute to 1 hour
- **Sensor entities** — filename, creation timestamp, and photo count per album
- **Select entities** — change crop mode, selection mode, and update interval live from the UI
- **Services** — `next_media` and `next_media_all` for use in automations

---

## Installation

### Via HACS (recommended)

1. In HACS, go to **Integrations → Custom repositories**
2. Add `https://github.com/Seekersdk/HA-Immich` as type **Integration**
3. Find **Immich Photos** and click **Install**
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/immich_photos` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Immich Photos**
3. Enter your Immich URL (e.g. `http://192.168.1.100:2283`) and API key
   - Get your API key: Immich web → Account Settings → API Keys → New API Key
4. Select which albums to expose (Favorites, All Photos, or any of your albums)

To add or change albums later, click **Configure** on the integration card.

---

## Entities created per album

| Platform | Entity | Description |
|---|---|---|
| `camera` | `{Album} Media` | Current photo — use in picture-entity or picture cards |
| `sensor` | `{Album} Filename` | Filename of the current photo |
| `sensor` | `{Album} Creation Timestamp` | Date and time the photo was taken |
| `sensor` | `{Album} Media Count` | Number of photos in the pool |
| `select` | `{Album} Image Selection Mode` | Random or Album order |
| `select` | `{Album} Crop Mode` | Original / Crop / Combine Images |
| `select` | `{Album} Update Interval` | How often to auto-advance (1 min – 1 hour) |

All entities for an album are grouped under a single device in **Settings → Devices & Services**.

---

## Crop Modes

### Original
Photo is scaled to fit the card's dimensions while preserving the aspect ratio (letterboxed). Best for preserving composition.

### Crop
Photo is center-cropped to fill the target size exactly. No letterboxing, but edges may be trimmed.

### Combine Images
When the current photo is **portrait** (taller than wide), a second portrait photo is automatically picked from the pool and placed **above and below** in a single portrait frame.

```
┌──────────────┐
│              │
│   Photo 1    │
│              │
├──────────────┤
│              │
│   Photo 2    │
│              │
└──────────────┘
```

This fills a portrait frame with two photos instead of wasting space with a single cropped image — great for photo frame dashboards and screensavers.

---

## Services

### `immich_photos.next_media`
Advance to the next photo for one or more specific camera entities.

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

### Screensaver with lovelace-wallpanel
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

Set **Crop Mode** to `Combine Images` and `image_fit: cover` for best results.

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

---

## How It Works

1. On setup, the integration calls Immich's `POST /api/search/metadata` (paginated) to build a local **asset pool** for each album. This pool is cached for **3 hours**.
2. On each update interval tick (default 5 min), it picks the next image — randomly or in album order.
3. If **Combine Images** mode is active and the selected photo is portrait, a second portrait photo is picked from the pool and both are composited above and below each other using Pillow.
4. The resulting JPEG is served to HA's camera platform and displayed on dashboards.

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

## Requirements

- Home Assistant 2023.x or newer
- Immich 1.90+ (requires `POST /api/search/metadata`)
- Python package: `Pillow>=10.0.0` (auto-installed)

---

## Credits

- [outadoc/immich-home-assistant](https://github.com/outadoc/immich-home-assistant) — the original Immich integration for Home Assistant that this project builds upon
- [Immich](https://immich.app) — the self-hosted photo management server
