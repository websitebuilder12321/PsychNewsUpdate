# Psych Research Daily — Website Setup

## Quick Setup

### 1. Push this folder to GitHub
Open Terminal and run:

```bash
cd ~/Desktop/PsychResearchDaily/site
git init
git add .
git commit -m "Initial commit — Psych Research Daily site"
git branch -M main
git remote add origin https://github.com/websitebuilder12321/PsychNewsUpdate.git
git push -u origin main
```

### 2. Enable GitHub Pages
- Go to https://github.com/websitebuilder12321/PsychNewsUpdate
- Click **Settings** → **Pages** (left sidebar)
- Under **Source**, select **Deploy from a branch**
- Select **main** branch, **/ (root)** folder
- Click **Save**

Your site will be live at: **https://websitebuilder12321.github.io/PsychNewsUpdate/**

### 3. Enable the daily auto-update
- Go to https://github.com/websitebuilder12321/PsychNewsUpdate/actions
- You should see the "Daily Newsletter Update" workflow
- Click **Enable** if prompted
- It runs automatically at 6:00 AM ET every day
- You can also trigger it manually: Actions → Daily Newsletter Update → Run workflow

### 4. Share with your team
Send your coworkers the URL and the access code: **1111**

To change the code later, generate a new SHA-256 hash at https://emn178.github.io/online-tools/sha256.html
and update the `VALID_HASH` value in `index.html`.

## How It Works
- **index.html** — Passcode gate (code: 1111)
- **newsletter.html** — The actual newsletter (redirects to login if not authenticated)
- **scripts/** — Python fetcher + HTML builder
- **.github/workflows/** — GitHub Actions for daily auto-updates
- The daily action fetches fresh articles from PubMed, builds the HTML, and commits it
