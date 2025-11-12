# 🚀 Deployment Guide: Public Website + Private Data

## Architecture Overview

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  GitHub Actions │ ───> │  Private GitHub  │ <─── │ Vercel Function │
│  (Scraper)      │      │  Repository      │      │  (API Proxy)    │
└─────────────────┘      └──────────────────┘      └────────┬────────┘
                                                              │
                                                              ▼
                                                    ┌─────────────────┐
                                                    │  Public Website │
                                                    │  (Vercel/Any)   │
                                                    └─────────────────┘
```

## 🎯 Step-by-Step Deployment

### Part 1: GitHub Setup (Private Data Storage)

1. **Create PRIVATE GitHub repository**
   - Name: `election-tracker-data`
   - Visibility: **Private**

2. **Push scraper code to private repo**
   ```powershell
   cd "C:\Users\Abhinand\OneDrive\VS Code\Tracker"
   
   # Add files (exclude public website files for now)
   git init
   git add scraper.py requirements.txt .github/
   git commit -m "Private data scraper"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/election-tracker-data.git
   git push -u origin main
   ```

3. **GitHub Actions will run every 5 minutes** and update `seat.json` in private repo

---

### Part 2: Vercel Setup (API Proxy - Free)

1. **Create GitHub Personal Access Token**
   - Go to: GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token (classic)
   - Name: `Election Tracker API`
   - Permissions: Check **`repo`** (full control)
   - Copy the token (save it securely!)

2. **Create new folder for API**
   ```powershell
   # In a NEW folder (or use this one)
   # Make sure you have: api/election-data.js and vercel.json
   ```

3. **Deploy to Vercel**
   
   **Option A: Using Vercel CLI (Recommended)**
   ```powershell
   # Install Vercel CLI
   npm install -g vercel
   
   # Login to Vercel
   vercel login
   
   # Deploy
   vercel
   
   # Follow prompts:
   # - Set up and deploy? Yes
   # - Which scope? Your account
   # - Link to existing project? No
   # - Project name? election-tracker-api
   # - Directory? ./
   # - Override settings? No
   ```

   **Option B: Using Vercel Dashboard**
   - Go to [vercel.com](https://vercel.com)
   - Click "Add New" → "Project"
   - Import from Git (if you pushed api/ to a repo) OR upload folder
   - Deploy

4. **Set Environment Variables in Vercel**
   - Go to your project → Settings → Environment Variables
   - Add these variables:
     - `GITHUB_USER` = your GitHub username
     - `GITHUB_REPO` = `election-tracker-data`
     - `GITHUB_TOKEN` = your personal access token from step 1
   - Click "Save"
   - **Redeploy** the project for changes to take effect

5. **Get your API URL**
   - After deployment, you'll get: `https://your-project.vercel.app`
   - Your API endpoint: `https://your-project.vercel.app/api/election-data`

---

### Part 3: Deploy Public Website

**Option A: Vercel (Same Project)**
1. Add `index-public.html` to your Vercel project
2. Rename it to `index.html`
3. Update the API_URL in the file to your Vercel API endpoint
4. Deploy!

**Option B: Netlify/Any Static Host**
1. Use `index-public.html` (rename to `index.html`)
2. Update API_URL to: `https://your-project.vercel.app/api/election-data`
3. Deploy to any static hosting service

**Option C: GitHub Pages (Public Repo)**
1. Create a NEW public repository: `election-tracker-website`
2. Add only `index-public.html` (renamed to `index.html`)
3. Update API_URL
4. Enable GitHub Pages
5. Website: `https://YOUR-USERNAME.github.io/election-tracker-website/`

---

## 🔐 Security Architecture

### What's Private:
- ✅ Scraper code (in private GitHub repo)
- ✅ GitHub token (in Vercel environment variables)
- ✅ Raw data files (in private repo)

### What's Public:
- ✅ Website HTML/CSS/JS (no sensitive data)
- ✅ API endpoint (but requires no auth - publicly accessible data)

### Data Flow:
1. GitHub Actions scrapes → saves to private repo
2. Public website requests data from Vercel API
3. Vercel API fetches from private GitHub (using token)
4. Vercel API returns data to website
5. **Token never exposed to browser**

---

## 💰 Cost Analysis (All FREE)

| Service | Free Tier | Your Usage |
|---------|-----------|------------|
| GitHub Actions | 2000 min/month | ~18 hours/month ✅ |
| GitHub Private Repo | Unlimited | 1 repo ✅ |
| Vercel Hosting | 100 GB bandwidth | Minimal ✅ |
| Vercel Functions | 100 GB-hours | Minimal ✅ |
| **TOTAL** | **$0/month** | ✅ |

---

## 🧪 Testing

1. **Test API endpoint directly:**
   ```
   https://your-project.vercel.app/api/election-data
   ```
   Should return JSON with election data

2. **Test website:**
   Open your deployed website, should load data automatically

3. **Test auto-refresh:**
   Wait 60 seconds, data should refresh

---

## 🔧 Alternative: Simple CORS Proxy

If you want even simpler (no Vercel account needed):

### Use a public CORS proxy:
```javascript
// In index-public.html, change API_URL to:
const API_URL = 'https://api.allorigins.win/raw?url=' + 
  encodeURIComponent('https://api.github.com/repos/USER/REPO/contents/seat.json');

// Add GitHub token to request headers
// Note: This exposes your token! Not recommended for sensitive data
```

⚠️ **Not recommended** - exposes token in browser, rate limits

---

## 📝 Quick Start Commands

```powershell
# 1. Deploy scraper to private GitHub
git init
git add scraper.py requirements.txt .github/
git commit -m "Private scraper"
git remote add origin https://github.com/YOUR-USER/election-tracker-data.git
git push -u origin main

# 2. Deploy API to Vercel
npm install -g vercel
vercel
# Set environment variables in Vercel dashboard

# 3. Update and deploy website
# Edit index-public.html with your API URL
# Deploy to any static host
```

---

## 🎉 Final Result

- ✅ **Data**: Scraped every 5 minutes → Private GitHub
- ✅ **API**: Secure proxy on Vercel
- ✅ **Website**: Public, accessible to anyone
- ✅ **Cost**: $0
- ✅ **Security**: Token never exposed

Your website: `https://your-site.com`  
Updates automatically every 60 seconds!
