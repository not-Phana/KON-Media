# KON Media — Neumorphic Media Workspace Design System

## 1. Design Rationale & Philosophy

**KON Media** is a desktop-first personal media utility engineered for Windows 11. Rather than adopting an exaggerated, impractical neumorphic aesthetic composed solely of low-contrast blurry shadows, KON Media implements a **Tactile Neumorphic Media Workspace**:

1. **Selective Tactility**: Raised soft-UI treatment is reserved for primary action controls, badges, and segmented toggles. Recessed / inset styling is applied to the URL input field and log monitors.
2. **Modern Dark Workspace**: Built on a refined, deep charcoal foundation that eliminates eye strain and maintains visual calm during extended desktop sessions.
3. **High Usability & Contrast**: Strict adherence to WCAG AA contrast standards. Structural boundaries are reinforced with crisp 1px borders rather than relying on shadow blur alone.
4. **Instant Affordance**: Buttons visibly press inward on active states; focus indicators use sharp, vibrant mint rings; status tags provide unmistakable operational clarity.

---

## 2. Color Palette & Design Tokens

### Core Foundation
| Token | Hex Value | Role / Usage |
| :--- | :--- | :--- |
| `--bg-main` | `#17191D` | Global canvas background |
| `--surface-card` | `#202329` | Workspace cards, panels, and container surfaces |
| `--surface-elevated` | `#272B32` | Raised buttons, active tab pills, floating modals |
| `--surface-recessed` | `#131418` | Inset input bars, progress bar troughs, code blocks |
| `--border-subtle` | `#2D323B` | Soft divider borders |
| `--border-strong` | `#383D46` | Card edges, input borders, control outlines |

### Text & Content
| Token | Hex Value | Contrast Ratio (vs #17191D) | Role / Usage |
| :--- | :--- | :--- | :--- |
| `--text-primary` | `#F3F4F6` | ~14.2:1 (Passes AAA) | Primary headings, titles, active labels |
| `--text-secondary` | `#A5ABB5` | ~7.1:1 (Passes AA) | Metadata, subtitles, helper text, timestamps |
| `--text-muted` | `#6B7280` | ~3.8:1 (Supporting) | Disabled labels, subtle placeholders |

### Semantic Accents
| Token | Hex Value | Meaning / Usage |
| :--- | :--- | :--- |
| `--accent-primary` | `#8BC5B0` | Brand identity, primary analyze action, active highlights |
| `--accent-hover` | `#9CD4C0` | Hover state for primary accent controls |
| `--status-success` | `#72C69A` | Download completed, dependency verified, healthy status |
| `--status-warning` | `#E8BE72` | Missing optional dependency (ffmpeg), retry state, slow speed |
| `--status-error` | `#EF8585` | Download failed, invalid URL, network timeout, unsupported source |
| `--status-info` | `#70B2D9` | Format analysis, metadata extraction, queue waiting |

---

## 3. Elevation & Neumorphic Shadow Recipes

Neumorphic depth in KON Media is calculated using dual light-source angles (`-135deg` light highlight and `45deg` ambient shadow):

### 1. Raised Interactive Surface (Buttons, Active Segment Pills)
```css
/* Normal state */
box-shadow:
  4px 4px 10px rgba(0, 0, 0, 0.45),
  -3px -3px 8px rgba(255, 255, 255, 0.04);
border: 1px solid #383D46;

/* Hover state */
box-shadow:
  6px 6px 14px rgba(0, 0, 0, 0.55),
  -4px -4px 10px rgba(255, 255, 255, 0.06);

/* Active / Pressed state */
box-shadow:
  inset 2px 2px 5px rgba(0, 0, 0, 0.6),
  inset -2px -2px 5px rgba(255, 255, 255, 0.03);
```

### 2. Recessed Surface (URL Input Field, Progress Bar Troughs)
```css
box-shadow:
  inset 3px 3px 8px rgba(0, 0, 0, 0.55),
  inset -2px -2px 6px rgba(255, 255, 255, 0.03);
border: 1px solid #2D323B;
```

### 3. Card Container (Restrained Workspace Panels)
```css
box-shadow:
  0 8px 24px -4px rgba(0, 0, 0, 0.4),
  0 2px 6px -1px rgba(0, 0, 0, 0.2);
border: 1px solid #2D323B;
```

---

## 4. Typography Scale

* **Primary Font**: `Inter`, `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, `Roboto`, `sans-serif`
* **Monospace Font**: `"JetBrains Mono"`, `Consolas`, `"Courier New"`, `monospace` (used strictly for URLs, bitrates, file sizes, format IDs, and duration timestamps)

| Level | Size | Weight | Line Height | Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Display Title** | `24px` (`1.5rem`) | `700` (Bold) | `1.2` | Workspace header / Brand |
| **Section Title** | `18px` (`1.125rem`) | `600` (SemiBold) | `1.3` | Card headers, queue titles |
| **Card Title** | `15px` (`0.9375rem`) | `600` (SemiBold) | `1.4` | Media title, history entry |
| **Body Regular** | `14px` (`0.875rem`) | `400` (Regular) | `1.5` | Form labels, descriptions |
| **Metadata Monospace** | `12px` (`0.75rem`) | `500` (Medium) | `1.4` | Resolution tags, speed, ETA |
| **Fine Print** | `11px` (`0.6875rem`) | `400` (Regular) | `1.4` | System status, version info |

---

## 5. Spacing & Border Radii

### Spacing Scale (8pt grid system)
* `space-1`: `4px`
* `space-2`: `8px`
* `space-3`: `12px`
* `space-4`: `16px`
* `space-6`: `24px`
* `space-8`: `32px`

### Radii Scale
* `radius-sm`: `6px` (Badges, format chips)
* `radius-md`: `10px` (Buttons, inputs, dropdown items)
* `radius-lg`: `14px` (Cards, task containers)
* `radius-xl`: `18px` (Workspace modal dialogs)
* `radius-full`: `9999px` (Status indicators, avatar pills)

---

## 6. Component Guidelines

### A. URL Search & Ingress Bar
* Recessed background (`#131418`) with crisp inner shadow.
* Monospace or sans font with automatic paste button pill.
* Integrated "Analyze" button with primary accent (`#8BC5B0`), soft raised elevation, and loading spinner animation during analysis.

### B. Media Info Card
* Displays rich thumbnail with rounded corners and duration badge overlay.
* Extracted metadata: Title, Uploader/Channel, Duration, Source domain tag.
* Format selection pills: segmented tab between **Video (MP4)** and **Audio (MP3)** with quality dropdown (1080p, 720p, 480p, 320kbps, 192kbps).

### C. Active Download Task Cards
* Status badge indicating state: `Queued` (Gray), `Analyzing` (Blue), `Downloading` (Mint), `Processing/FFmpeg` (Amber), `Completed` (Green), `Failed` (Red), `Cancelled` (Muted).
* Live progress bar with smooth transition, percentage indicator, current speed (`MB/s`), and ETA.
* Cancel / Remove action button with tactile press feedback.

### D. Download History Table / Cards
* Minimalist card list showing completed file name, format, file size, timestamp, and a "Show in Folder" button using native OS file explorer integration.
* Action to clear history (with confirmation).

---

## 7. Accessibility & Motion

* **Contrast**: All interactive text meets minimum 4.5:1 ratio against surface backgrounds.
* **Focus Rings**: Focused controls display an unmistakable `2px solid #8BC5B0` outline with `2px offset`.
* **Reduced Motion**: Respects `prefers-reduced-motion: reduce`. All transitions and progress bar updates disable spring animations in reduced motion mode.
* **Keyboard Navigation**: Full Tab navigation support across input bar, format pills, download button, and history table.
