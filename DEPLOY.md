# RelationshipOS — Deployment Guide

**Time required:** 5-10 minutes per platform. Pick one.

This guide walks you through deploying the RelationshipOS backend to a permanent URL that does not sleep. Three platforms are supported, listed in order of recommendation.

---

## Table of Contents

1. [Quick Summary](#quick-summary)
2. [Option A: Render.com (Recommended)](#option-a-rendercom-recommended)
3. [Option B: Railway.app](#option-b-railwayapp)
4. [Option C: Fly.io](#option-c-flyio)
5. [After Deployment: Connect the Frontend](#after-deployment-connect-the-frontend)
6. [Environment Variables Reference](#environment-variables-reference)
7. [Troubleshooting](#troubleshooting)

---

## Quick Summary

| Platform | Free Tier | Sleep Behaviour | Deploy Method | Credit Card |
|----------|-----------|-----------------|---------------|-------------|
| **Render** | 750 hrs/month | Sleeps after 15 min idle, wakes on request (~30s cold start) | GitHub repo + Blueprint | Not required for free tier |
| **Railway** | $5 credit trial | No sleep on trial | GitHub repo | Required after trial |
| **Fly.io** | 3 shared VMs free | Auto-stop/start (configurable) | CLI + Dockerfile | Required (not charged on free tier) |

> **Recommendation:** Start with **Render**. It is the simplest, requires no credit card, and the Blueprint file (`render.yaml`) is already configured.

---

## Prerequisites (All Platforms)

1. **Push this repo to GitHub:**

```bash
# Create a new repo at https://github.com/new (name: relationshipos-api)
# Then push:
cd relationshipos
git remote add origin https://github.com/YOUR_USERNAME/relationshipos-api.git
git branch -M main
git push -u origin main
```

> If you do not have git configured, you can also upload via GitHub's web interface: drag-and-drop the project folder into a new repository.

---

## Option A: Render.com (Recommended)

**Time: ~3 minutes. No credit card required.**

### Step 1 — Create a Render Account

Go to [dashboard.render.com/register](https://dashboard.render.com/register) and sign up with GitHub (recommended for automatic repo access).

### Step 2 — Deploy via Blueprint

1. Go to [dashboard.render.com/select-repo?type=blueprint](https://dashboard.render.com/select-repo?type=blueprint)
2. Select your `relationshipos-api` repository
3. Render reads the `render.yaml` file and shows the service configuration
4. Click **Apply** — that is it

Render will:
- Build the Docker image
- Auto-generate a secure `JWT_SECRET_KEY`
- Deploy to a URL like `https://relationshipos-api.onrender.com`
- Set up health checks at `/health`

### Step 3 — Verify

```bash
curl https://relationshipos-api.onrender.com/health
# → {"status":"healthy"}
```

### Step 4 — Note Your URL

Your permanent backend URL will be:
```
https://relationshipos-api.onrender.com/api/v1
```

> **Note:** On the free tier, the service sleeps after 15 minutes of inactivity. The first request after sleep takes approximately 30 seconds. Subsequent requests are fast. For a production app, upgrade to the $7/month Starter plan to eliminate sleep.

---

## Option B: Railway.app

**Time: ~5 minutes. Credit card required after free trial.**

### Step 1 — Create a Railway Account

Go to [railway.com](https://railway.com) and sign up with GitHub.

### Step 2 — Create a New Project

1. Click **New Project** → **Deploy from GitHub Repo**
2. Select your `relationshipos-api` repository
3. Railway auto-detects the `Dockerfile` and `railway.json`

### Step 3 — Set Environment Variables

In the Railway dashboard, go to your service → **Variables** tab and add:

| Variable | Value |
|----------|-------|
| `JWT_SECRET_KEY` | (click "Generate" or paste a random 32-char string) |
| `CORS_ORIGINS` | `*` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/relationshipos.db` |

### Step 4 — Deploy

Railway deploys automatically when you push to GitHub. Your URL will be something like:
```
https://relationshipos-api-production.up.railway.app/api/v1
```

### Step 5 — Generate a Public Domain

Go to **Settings** → **Networking** → **Generate Domain** to get a public URL.

---

## Option C: Fly.io

**Time: ~5 minutes. Credit card required (not charged on free tier).**

### Step 1 — Install the Fly CLI

```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

### Step 2 — Sign Up and Log In

```bash
fly auth signup    # Opens browser to create account
fly auth login     # Or log in if you already have an account
```

### Step 3 — Launch the App

```bash
cd relationshipos
fly launch --copy-config --no-deploy
```

When prompted:
- App name: `relationshipos-api` (or accept the generated name)
- Region: `syd` (Sydney — closest to NZ)
- Do NOT set up a database (we use SQLite)

### Step 4 — Set Secrets

```bash
fly secrets set JWT_SECRET_KEY=$(openssl rand -hex 32)
```

### Step 5 — Deploy

```bash
fly deploy
```

Your URL will be:
```
https://relationshipos-api.fly.dev/api/v1
```

### Step 6 — Verify

```bash
curl https://relationshipos-api.fly.dev/health
# → {"status":"healthy"}
```

---

## After Deployment: Connect the Frontend

Once you have a permanent backend URL, you need to update the frontend to point at it.

### Option 1: Use the Patch Script (Quick, No Rebuild)

A script is included that downloads the current deployed frontend, patches the hardcoded backend URL, and outputs a new static site ready to redeploy:

```bash
cd relationshipos
./scripts/patch_frontend.sh https://YOUR-BACKEND-URL.onrender.com/api/v1
```

This creates a `frontend_patched/` directory. Deploy it as a static site:

```bash
# Netlify (free)
cd frontend_patched
npx netlify deploy --prod --dir=.

# Or Vercel (free)
cd frontend_patched
npx vercel --prod
```

### Option 2: Rebuild the Frontend (Proper, Long-Term)

If you have access to the frontend source code, update the API configuration:

1. Create a `.env` file in the frontend project root:
```
VITE_API_URL=https://YOUR-BACKEND-URL.onrender.com/api/v1
```

2. Update `client/src/lib/api.ts` (or wherever the axios instance is created):
```typescript
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const api = axios.create({ baseURL: API_BASE, ... });
```

3. Rebuild and redeploy:
```bash
pnpm build
# Deploy the dist/ folder
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./data/relationshipos.db` | Database connection string. Use `postgresql+asyncpg://...` for PostgreSQL. |
| `JWT_SECRET_KEY` | **Yes** | `change-me-in-production` | Secret key for signing JWT tokens. **Must be changed in production.** |
| `CORS_ORIGINS` | No | `*` | Comma-separated list of allowed origins. Set to your frontend URL in production. |
| `APP_NAME` | No | `RelationshipOS` | Application name shown in API docs. |
| `APP_VERSION` | No | `1.0.0` | Application version. |
| `PORT` | No | `8000` | Server port. Most platforms set this automatically. |

---

## Troubleshooting

### "502 Bad Gateway" after deploy

The service is still starting. Wait 30 seconds and try again. Check the deploy logs in your platform's dashboard.

### "Connection refused" from frontend

The frontend is pointing at the old sandbox URL. Run the patch script or rebuild the frontend with the new backend URL.

### Database is empty after deploy

The `seed_data.py` script runs automatically on every container start. If you see empty responses, check the deploy logs for errors during seeding.

### CORS errors in browser console

Set `CORS_ORIGINS` to your frontend's exact URL (e.g., `https://relateapp-q2dmbaem.manus.space`). Using `*` works for development but is not recommended for production.

### Upgrading to PostgreSQL

1. Provision a PostgreSQL database (Render, Railway, and Fly all offer managed Postgres)
2. Set `DATABASE_URL` to the PostgreSQL connection string:
   ```
   postgresql+asyncpg://user:password@host:5432/relationshipos
   ```
3. Remove `aiosqlite` from requirements and add `asyncpg` (already included)
4. Redeploy — tables are created automatically on startup

---

## Test Credentials

After deployment with seed data:

| Email | Password | Role |
|-------|----------|------|
| `todd@eves.co.nz` | `password123` | Primary user (Todd Hilleard) |
| `demo@relationshipos.app` | `demo1234` | Demo user |

---

## API Documentation

Once deployed, visit:
- **Swagger UI:** `https://YOUR-URL/docs`
- **ReDoc:** `https://YOUR-URL/redoc`
- **Health Check:** `https://YOUR-URL/health`
