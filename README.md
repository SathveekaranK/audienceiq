# AudienceIQ - Know Your Audience

## Project Overview
AudienceIQ is an AI-powered platform that helps YouTube creators understand their audience by analyzing comments on their videos. Instead of just looking at view counts and likes, AudienceIQ uses sentiment analysis, topic modelling and clustering to tell you what your viewers actually think, want, and complain about.

## What It Does
- **Analyses any YouTube video** - paste a link and pull its real comments
- **Classifies emotions** - influenced / triggered / hate / love / curious
- **Analyses sentiment** (positive / negative / neutral) with VADER
- **Finds topics** your audience talks about most with LDA topic modelling
- **Groups viewers** into segments with K-Means clustering on TF-IDF vectors
- **Identifies problems** viewers keep mentioning (pain points)
- **Suggests content** you should make next
- **Tracks trends** over time and saves reports you can compare

## Project Structure
```
audienceiq/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # DB connection + SQLite fallback
│   ├── models.py            # SQLAlchemy models
│   ├── seed_demo.py         # One-video VJ Siddhu seed loader
│   ├── requirements.txt
│   ├── routes/
│   │   ├── api.py           # Action endpoints (analyse, collect, generate)
│   │   ├── insights.py      # Read endpoints (dashboard, lists, summaries)
│   │   └── videos.py        # YouTube video fetching + analysis
│   └── services/
│       ├── youtube.py       # Keyless YouTube metadata + comments
│       ├── emotions.py      # Influenced / triggered / hate detection
│       ├── pain_points.py   # Complaint detection
│       ├── content_demand.py
│       ├── text_preprocessor.py
│       ├── sentiment_analyzer.py
│       ├── topic_modeler.py
│       └── clustering.py
├── frontend/
│   ├── src/
│   │   ├── components/      # UI kit, charts, layout, feedback
│   │   ├── views/           # One component per dashboard page
│   │   ├── lib/             # API client, hooks, formatters
│   │   └── App.tsx
│   ├── vite.config.mts
│   └── package.json
├── scripts/                 # Helper scripts used by the launcher
├── start.cmd                # Windows: double-click to run everything
├── start.ps1                # PowerShell: one-command launcher
└── README.md
```

## Prerequisites
1. **Python 3.9+**
2. **Node.js 18+**
3. **Git** (only to download the project)

> PostgreSQL is **optional**. If it is not running, the backend automatically
> falls back to a local SQLite file (`backend/audienceiq.db`).

---

## Quick Start (ONE COMMAND)

### Windows - double-click `start.cmd`

Or from PowerShell / cmd:

```powershell
.\start.cmd
```

That single command:
1. Checks that Python and Node.js are installed
2. Installs backend dependencies if any are missing
3. Installs frontend dependencies if `node_modules` is missing
4. Seeds one verified VJ Siddhu Vlogs upload and up to 60 real comments
   (the first run prints a one-time password for the `demo` account)
5. Starts the backend on `http://127.0.0.1:8000`
6. Starts the frontend on `http://localhost:3001`
7. Opens your browser at `http://localhost:3001`

### PowerShell - keep both servers in one terminal

```powershell
.\start.ps1
```

Press `Ctrl+C` to stop both.

### PowerShell - separate windows

```powershell
.\start.ps1 -Separate
```

---

## Using the app

1. Open `http://localhost:3001` and sign in as `demo` with the one-time
   password printed by the seeder. You can also register a separate account.
2. The seeded VJ Siddhu channel is ready; press **Run full analysis** on the Overview page (or use the buttons on
   each page) to compute sentiment, topics and segments.
3. Explore the eleven pages:

| Page | What it shows |
|---|---|
| **Overview** | KPIs, sentiment donut, top topics, segments, best performing video |
| **Sentiment** | Sentiment over time (7/30/90/365 day windows), daily breakdown table |
| **Emotions** | Influenced / triggered / hate / love / curious, with examples |
| **Topics** | Discovered topics ranked by mention volume, with words and sample comments |
| **Segments** | Audience clusters named after their keywords, with example comments |
| **Pain Points** | Recurring complaints, ranked, each with the comments that triggered it |
| **Content Ideas** | What viewers are asking you to make next, with confidence scores |
| **Analyse Video** | Paste a YouTube link and pull that video's real comments |
| **Videos** | Per-video views, likes, comment counts and sentiment split |
| **Comments** | Every comment, searchable and filterable by sentiment, paginated |
| **Reports** | Saved analysis snapshots for a date range |

4. Use the **channel picker** in the sidebar to switch channels, or
   **Add channel** to track a new one.
5. Use **Sign out** at the bottom of the sidebar to invalidate the current session.

---

## Analysing a real YouTube video

Go to **Content → Analyse Video** and paste any YouTube link:

```
https://www.youtube.com/watch?v=XXXXXXXXXXX
https://youtu.be/XXXXXXXXXXX
https://www.youtube.com/shorts/XXXXXXXXXXX
```

Press **Fetch & analyse**. AudienceIQ will:

1. Resolve the video's metadata (title, channel, views, publish date,
   thumbnail) straight from YouTube.
2. Download the real top-level comments, including the author name and
   like count.
3. Store them against the channel and video.
4. Run sentiment, emotion, topic, pain point and content demand analysis.

Afterwards the video appears in the **Analyse Video** list and its channel in
the sidebar, where every other page works against it.

**No YouTube API key is required.** Comments and metadata are fetched through
YouTube's public InnerTube endpoints (the same ones the web player uses). If
you *do* have a YouTube Data API key, set `YOUTUBE_API_KEY` and it will be used
for metadata instead - it gives you a higher quota and more reliable stats.

### How far the analysis goes

The analysis is deliberately explainable and runs offline:

- **Sentiment** - VADER, with a transformer model available as an opt-in.
- **Emotions** - a weighted lexicon with intensity modifiers, negation
  handling and contrast markers. A comment can carry several emotions at
  once ("great video, but the pacing was too fast" is *love* **and**
  *triggered*). The strongest signal becomes the primary emotion; every
  emotion that cleared the threshold is kept so the dashboard can show
  overlaps. Emoji usage and ALL-CAPS are used as intensity signals.
- **Topics** - LDA over TF-IDF vectors. For non-Latin scripts (Tamil, Hindi,
  Chinese) the model switches to character n-grams so the clustering still
  works. Topics are then *named* after the words people actually used, ranked
  by how distinctive they are to that topic - not by raw model output.
- **Pain points** - complaint phrases are detected across all comments, not
  just negative ones, because most real complaints read as positive to a
  sentiment model ("great video, but too fast").
- **Segments** - K-Means over TF-IDF vectors of the comment text, with each
  segment named after its most common keywords.

### Seeding / resetting demo data

The default seed contains exactly one video: VJ Siddhu Vlogs' November 11,
2026 upload, `5j4GMySx_Ac` (`Egypt Series | Ep 01`). Metadata and comments are
refreshed from YouTube when the network is available.

```bash
cd backend
python seed_demo.py                         # seed the verified default video
python seed_demo.py --comments 100          # choose the comment limit (max 500)
python seed_demo.py --video <youtube-url>   # seed a different single video
python seed_demo.py --reset                 # wipe and rebuild the seeded channel
python seed_demo.py --offline               # use bundled fallback metadata/comments
```

---

## Manual Setup (if you prefer to run each server yourself)

### Backend

```bash
cd backend
python -m venv venv
```
- **Windows**: `venv\Scripts\activate`
- **Mac/Linux**: `source venv/bin/activate`

```bash
pip install -r requirements.txt
python seed_demo.py    # optional demo data
python main.py
```

The backend starts at `http://127.0.0.1:8000`.
Interactive API docs: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The site runs at `http://localhost:3001` (opens automatically).

### Production build

```bash
cd frontend
npm run build     # outputs to frontend/dist
npm run preview   # serves the built bundle
```

---

## Database Configuration

The backend picks its database automatically:

| Priority | Source | Example |
|---|---|---|
| 1 | `DATABASE_URL` env var or `backend/.env` | `postgresql://user:pass@localhost:5432/audienceiq` |
| 2 | PostgreSQL on localhost | `postgresql://localhost/audienceiq` |
| 3 | SQLite fallback | `backend/audienceiq.db` |

To force a specific database, create `backend/.env`:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/audienceiq
```

Tables are created automatically on startup - there is no migration step.

### Security configuration

- Every `/api/v1` workspace endpoint requires an `Authorization: Bearer <token>`
  header. Registration and login return an opaque session token; logout revokes it.
- Session tokens expire after 7 days by default. Set `AUTH_SESSION_DAYS` to a
  value from 1 to 90 to change this.
- Set `ALLOWED_ORIGINS` to a comma-separated list of exact frontend origins in
  deployed environments, and set `ENV=production` to disable interactive API docs.
- Set `SEED_DEMO_PASSWORD` before seeding if you do not want a random one-time
  demo password printed to the console.

---

## API Reference

All endpoints are prefixed with `/api/v1`.

### Auth
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create an account |
| POST | `/auth/login` | Sign in |
| POST | `/auth/logout` | Revoke the current bearer session |

### Workspace
| Method | Path | Purpose |
|---|---|---|
| GET | `/creators` | List all tracked channels with stats |
| GET | `/creators/{id}` | One channel's profile and stats |
| POST | `/creators/add` | Track a new channel |
| GET | `/creators/search?query=` | Search channels |
| DELETE | `/creators/{id}` | Delete a channel and all its data |

### Content
| Method | Path | Purpose |
|---|---|---|
| GET | `/creators/{id}/videos` | Videos with per-video sentiment stats |
| GET | `/creators/{id}/comments` | Comments with `?sentiment=`, `?search=`, `?limit=`, `?offset=` |
| POST | `/comments/collect/{post_id}` | Collect comments for a video |

### YouTube video analysis
| Method | Path | Purpose |
|---|---|---|
| POST | `/videos/resolve` | Preview a video's metadata without saving |
| POST | `/videos/analyze` | Fetch a video's real comments and analyse them |
| POST | `/videos/{id}/analyze` | Re-fetch and re-analyse a tracked video |
| GET | `/videos/workspace` | Every analysed video with its stats |
| GET | `/videos/{id}/emotions` | Emotion breakdown for one video |

### Analysis
| Method | Path | Purpose |
|---|---|---|
| POST | `/analysis/sentiment/bulk/{id}` | Analyse sentiment for every comment |
| POST | `/analysis/sentiment/{comment_id}` | Analyse one comment |
| GET | `/analysis/sentiment/distribution/{id}` | Sentiment split (`?post_id=` to scope to a video) |
| GET | `/analysis/sentiment/timeseries/{id}?days=` | Daily sentiment trend |
| POST | `/analysis/emotions/{id}` | Classify comments by emotion |
| GET | `/analysis/emotions/{id}` | Emotion breakdown (`?post_id=` to scope to a video) |
| POST | `/analysis/topics/{id}` | Run topic modelling |
| GET | `/analysis/topics/{id}` | Stored topics with words and sample comments |
| POST | `/analysis/segmentation/{id}` | Cluster the audience |
| GET | `/analysis/segments/{id}` | Stored segments |
| POST | `/analysis/pain-points/{id}` | Detect complaints |
| GET | `/analysis/pain-points/{id}` | Stored pain points |
| POST | `/analysis/content-requests/{id}` | Detect content demand |
| GET | `/analysis/content-requests/{id}` | Stored content demand |
| GET | `/analysis/engagement/{id}` | Engagement metrics |
| GET | `/analysis/overview/{id}` | What analysis data exists so far |

### Dashboard & Reports
| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard/summary/{id}` | Everything the Overview page needs |
| GET | `/reports/{id}` | Saved reports |
| POST | `/reports/generate/{id}` | Generate a report for a date range |
| GET | `/intelligence-report/{id}/{report_id}` | Full report detail |

---

## Technology Used
- **Backend**: Python, FastAPI, Uvicorn, SQLAlchemy 2.x
- **Frontend**: React 19, Vite, Tailwind CSS v4, TypeScript
- **Database**: PostgreSQL (production) with SQLite fallback (development)
- **AI/ML**: VADER sentiment analysis, LDA topic modelling, K-Means clustering, TF-IDF vectors
- **NLP**: NLTK for text preprocessing
- **Charts**: hand-rolled dependency-free SVG charts (donut, bar list, trend line)

## Project Phases (Based on the PRD)
1. **MVP Core**: User login, YouTube search, comment collection, basic sentiment
2. **Advanced Analytics**: Topic modeling, audience segmentation, pain point detection
3. **Intelligence Engine**: Content recommendations, advanced NLP
4. **Extended Platform**: Instagram integration, multi-creator comparison

## Developer Notes
- Action endpoints live in `backend/routes/api.py`; read/aggregate endpoints live
  in `backend/routes/insights.py`.
- Database models: `backend/models.py`. Connection setup: `backend/database.py`.
- NLP services: `backend/services/`.
- Frontend UI kit: `frontend/src/components/ui.tsx`.
- Charts: `frontend/src/components/charts.tsx`.
- API client: `frontend/src/lib/api.ts`. Data hooks: `frontend/src/lib/hooks.ts`.
- The `@/` import alias maps to `frontend/src/` (configured in `vite.config.mts`).
- Point the frontend at a different backend with `VITE_API_URL`.

## Troubleshooting
- **"Python was not found"**: Install Python 3.9+ and make sure it is on your PATH
- **"Node.js was not found"**: Install Node.js 18+ from nodejs.org
- **"Cannot reach the API"**: The backend is not running. Check the backend window.
- **If npm install fails**: Try `npm install --legacy-peer-deps`
- **Port 8000 or 3001 in use**: Stop the old process, or change the port in
  `backend/main.py` / `frontend/vite.config.mts`
- **Want a clean slate**: Delete `backend/audienceiq.db`, then run
  `python seed_demo.py` to rebuild the demo data.
- **First run is slow**: The backend loads NLTK data and transformer models on
  startup. This takes up to a minute the first time.

## License
This is an individual project for educational purposes following the AudienceIQ PRD specifications.
