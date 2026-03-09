# RelationshipOS Backend — Deployment Guide for Todd

**Total time: about 10 minutes. No coding required.**

This guide walks you through three steps:
1. Create a GitHub repository and upload the backend code
2. Connect it to Render.com to host it permanently
3. Test that it is working

---

## What You Need Before Starting

- The `RelationshipOS-Backend.zip` file (you have this)
- A web browser
- An email address to sign up with

---

## STEP 1 — Create a GitHub Account (skip if you already have one)

1. Go to **[github.com/signup](https://github.com/signup)**
2. Enter your email address, create a password, and choose a username
   - Suggested username: `toddnztodd`
3. Verify your email address when GitHub sends you a confirmation email
4. You are now logged in to GitHub

---

## STEP 2 — Create the Repository on GitHub

A "repository" is just a folder on GitHub that stores your code.

1. Go to **[github.com/new](https://github.com/new)**

2. Fill in the form exactly like this:

   | Field | What to type |
   |-------|-------------|
   | **Repository name** | `relationshipos-api` |
   | **Description** | RelationshipOS backend API |
   | **Public / Private** | Select **Public** |
   | **Add a README file** | Leave this **unticked** |

3. Click the green **"Create repository"** button at the bottom

4. You will land on a page that says "Quick setup". **Leave this page open** — you will come back to it.

---

## STEP 3 — Unzip and Upload the Code

### 3a — Unzip the file

- **On Mac:** Double-click `RelationshipOS-Backend.zip` — a folder called `relationshipos` will appear
- **On Windows:** Right-click `RelationshipOS-Backend.zip` → click **"Extract All"** → click **Extract**

### 3b — Upload to GitHub

1. Go back to the GitHub page from Step 2 (your new empty repository)

2. Click the link that says **"uploading an existing file"**
   - It appears in the sentence: *"...or create a new file or importing an existing repository"*
   - If you cannot see it, go to: `https://github.com/toddnztodd/relationshipos-api/upload/main`

3. Open the unzipped folder on your computer. You will see files and folders inside it (like `app`, `Dockerfile`, `requirements.txt`, etc.)

4. **Select everything inside the folder** (Cmd+A on Mac, Ctrl+A on Windows) and **drag it all** into the GitHub upload area in your browser

5. Wait for all files to finish uploading (you will see a list of file names appear)

6. Scroll down to the **"Commit changes"** section at the bottom of the page

7. In the first text box (where it says "Add files via upload"), type:
   ```
   Initial commit — RelationshipOS backend
   ```

8. Click the green **"Commit changes"** button

9. Wait about 30 seconds. When it finishes, you will see all your files listed in the repository. 

---

## STEP 4 — Create a Render.com Account

Render.com will host your backend so it is always available online.

1. Go to **[render.com](https://render.com)** and click **"Get Started for Free"**

2. Click **"Sign up with GitHub"** — this connects Render to your GitHub account automatically

3. Authorise Render to access your GitHub repositories when prompted

4. You are now logged in to Render

---

## STEP 5 — Deploy the Backend on Render

1. In the Render dashboard, click the **"New +"** button (top right)

2. Select **"Web Service"** from the dropdown

3. On the next screen, click **"Connect account"** next to GitHub if it is not already connected

4. You will see a list of your GitHub repositories. Find **`relationshipos-api`** and click **"Connect"**

5. Render will show you a configuration form. Fill it in like this:

   | Field | What to enter |
   |-------|--------------|
   | **Name** | `relationshipos-api` |
   | **Region** | `Oregon (US West)` or the closest to you |
   | **Branch** | `main` |
   | **Runtime** | `Docker` |
   | **Instance Type** | `Free` |

   > **Note:** Render should automatically detect the `Dockerfile` in your repository. If it asks for a "Build Command", leave it blank.

6. Scroll down to the **"Environment Variables"** section. Click **"Add Environment Variable"** and add these one at a time:

   | Key | Value |
   |-----|-------|
   | `JWT_SECRET_KEY` | Click **"Generate"** button next to this field (Render will create a secure random value for you) |
   | `CORS_ORIGINS` | `*` |
   | `DATABASE_URL` | `sqlite+aiosqlite:///./data/relationshipos.db` |

7. Click the **"Create Web Service"** button at the bottom

8. Render will now build and deploy your backend. This takes **3–5 minutes** the first time. You will see a log of what is happening — this is normal.

9. When it is done, the status at the top will change from **"In progress"** to **"Live"** (shown in green)

---

## STEP 6 — Find Your Permanent Backend URL

1. At the top of your Render service page, you will see a URL that looks like:
   ```
   https://relationshipos-api.onrender.com
   ```

2. Click that link. You should see:
   ```json
   {"app":"RelationshipOS","version":"1.0.0","status":"running","docs":"/docs"}
   ```

3. To test the health check, add `/health` to the URL:
   ```
   https://relationshipos-api.onrender.com/health
   ```
   You should see: `{"status":"healthy"}`

4. To see the full API documentation, add `/docs` to the URL:
   ```
   https://relationshipos-api.onrender.com/docs
   ```

**Your permanent backend URL is:**
```
https://relationshipos-api.onrender.com/api/v1
```

Write this down — you will need it to connect the frontend.

---

## STEP 7 — Connect the Frontend to the New Backend

The frontend app (relateapp-q2dmbaem.manus.space) currently points at the old sandbox URL. To reconnect it:

1. Send this URL to your developer:
   ```
   https://relationshipos-api.onrender.com/api/v1
   ```

2. Ask them to update `VITE_API_URL` in the frontend and redeploy

**Or**, if you want to do it yourself using the patch script included in the zip:

```bash
cd relationshipos
./scripts/patch_frontend.sh https://relationshipos-api.onrender.com/api/v1
```

This creates a `frontend_patched/` folder you can drag-and-drop onto Netlify or Vercel.

---

## Important Notes

### Free Tier Sleep Behaviour

On Render's free tier, the backend will go to sleep after **15 minutes of no activity**. The first request after it wakes up takes about **30 seconds**. Everything after that is fast.

To prevent sleeping, upgrade to Render's **Starter plan ($7/month)** in the Render dashboard under your service settings.

### Test Login Credentials

Once deployed, you can log in with:

| Email | Password |
|-------|----------|
| `todd@eves.co.nz` | `password123` |
| `demo@relationshipos.app` | `demo1234` |

### If Something Goes Wrong

- In the Render dashboard, click on your service → click **"Logs"** tab to see what happened
- Common fix: click **"Manual Deploy"** → **"Deploy latest commit"** to restart

---

## Summary

| Step | What you did |
|------|-------------|
| 1 | Created a GitHub account |
| 2 | Created a `relationshipos-api` repository |
| 3 | Uploaded all the backend code |
| 4 | Created a Render.com account |
| 5 | Deployed the backend as a Web Service |
| 6 | Got your permanent URL: `https://relationshipos-api.onrender.com` |
| 7 | Updated the frontend to use the new URL |

You now have a permanently hosted backend that will not disappear when the sandbox sleeps.
