# 🗳️ Live Election Results Tracker

Automated election results tracker that scrapes data every 5 minutes and provides a live web dashboard.

## 🚀 Features

- ✅ Automated scraping every 5 minutes via GitHub Actions
- ✅ Generates both CSV and JSON outputs
- ✅ Live web dashboard with auto-refresh
- ✅ Completely free hosting using GitHub
- ✅ No server maintenance required

## 📋 Setup Instructions

### Step 1: Create GitHub Repository

1. Go to [GitHub](https://github.com) and create a new repository
2. Name it something like `election-tracker`
3. Make it **Private** (keeps your data secure)
4. Initialize with a README (optional)

### Step 2: Push Your Code

Open terminal in your project folder and run:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
git push -u origin main
```

Replace `YOUR-USERNAME` and `YOUR-REPO-NAME` with your actual GitHub username and repository name.

### Step 3: Enable GitHub Actions

1. Go to your repository on GitHub
2. Click the **Actions** tab
3. If prompted, click "I understand my workflows, go ahead and enable them"
4. The workflow will start running automatically every 5 minutes

You can also manually trigger it:
- Go to **Actions** tab
- Click **Election Data Scraper** workflow
- Click **Run workflow** button

### Step 4: Create GitHub Personal Access Token (for private repo access)

1. Go to GitHub **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Click **Generate new token (classic)**
3. Name it "Election Tracker Access"
4. Select expiration (recommend "No expiration" for continuous access)
5. Check **only** the `repo` scope (Full control of private repositories)
6. Click **Generate token**
7. **COPY THE TOKEN** - you won't see it again!

### Step 5: Host Your Dashboard

**Option A: Local Hosting (Recommended)**
- Simply open `index.html` in your browser
- Data stays private on your machine
- Free and secure

**Option B: Private Web Host**
- Deploy to Vercel/Netlify with password protection
- Update `index.html` to use authenticated GitHub API:

```javascript
const DATA_URL = 'https://api.github.com/repos/YOUR-USERNAME/YOUR-REPO/contents/seat.json';
const TOKEN = 'YOUR_GITHUB_TOKEN'; // From Step 4

async function fetchElectionData() {
    const response = await fetch(DATA_URL, {
        headers: {
            'Authorization': `token ${TOKEN}`,
            'Accept': 'application/vnd.github.v3.raw'
        }
    });
    // ... rest of code
}
```

**Option C: Deploy to Private Server**
- Use any hosting platform you control
- Configure authentication/password protection
- Point to your GitHub repo with token authentication

## 📁 Project Structure

```
election-tracker/
├── .github/
│   └── workflows/
│       └── scraper.yml          # GitHub Actions workflow (runs every 5 mins)
├── scraper.py                    # Main scraper script
├── requirements.txt              # Python dependencies
├── index.html                    # Live dashboard webpage
├── seat.csv                      # Output CSV (auto-generated)
└── seat.json                     # Output JSON (auto-generated)
```

## 🔧 How It Works

1. **GitHub Actions** runs `scraper.py` every 5 minutes
2. Script scrapes election data from ECI website
3. Generates `seat.csv` and `seat.json` files
4. GitHub Actions commits the updated files back to the repo
5. **GitHub Pages** serves the `index.html` dashboard
6. Dashboard fetches latest `seat.json` every 60 seconds

## 💾 Data Format

### JSON Structure
```json
{
  "last_updated": "2025-11-13T10:30:00Z",
  "total_seats": 90,
  "data": [
    {
      "Seat": "Constituency Name",
      "Leading": "Party A",
      "Trailing": "Party B",
      "3rd Place": "Party C",
      "1": 50000,
      "2": 45000,
      "3": 30000,
      "Rest": 15000
    }
  ]
}
```

### CSV Format
```csv
Seat,Leading,Trailing,3rd Place,1,2,3,Rest
Constituency Name,Party A,Party B,Party C,50000,45000,30000,15000
```

## 🎨 Customization

### Change Scraping Interval

Edit `.github/workflows/scraper.yml`:
```yaml
schedule:
  - cron: '*/5 * * * *'  # Every 5 minutes
  # - cron: '*/10 * * * *'  # Every 10 minutes
  # - cron: '0 * * * *'     # Every hour
```

### Change Dashboard Refresh Rate

Edit `index.html`:
```javascript
let countdown = 60; // Refresh every 60 seconds
```

### Styling

All styles are in `index.html` inside the `<style>` tag. Modify colors, fonts, layout as needed.

## 🐛 Troubleshooting

### Actions Failing?
- Check the **Actions** tab for error logs
- Ensure repository is **Public**
- Verify all files are committed properly

### Dashboard Not Loading Data?
- Check browser console for errors (F12)
- Verify the `DATA_URL` points to correct GitHub raw URL
- Make sure `seat.json` exists in your repository

### Scraper Errors?
- Website structure might have changed
- Check Chrome driver compatibility
- Review logs in GitHub Actions

## 📊 Monitoring

- View workflow runs: **Actions** tab
- Check scraper logs: Click on any workflow run
- See commit history: **Commits** section

## 💰 Cost

**100% FREE** 
- GitHub Actions: 2000 minutes/month for **private repos** (Free tier)
- Running every 5 minutes uses ~2 seconds per run = ~18 hours/month
- Well within free tier limits!
- GitHub storage: Free for private repos

## � Privacy & Security

- **Private repository** - Only you can access the code and data
- Data is NOT publicly accessible
- Use Personal Access Token for any external dashboard access
- Can open `index.html` locally for completely offline viewing

## �📝 Notes

- First run may take longer (installing dependencies)
- Data updates appear on dashboard within 60 seconds
- GitHub Actions may have slight delays (±1-2 minutes)
- Private repos get 2000 free minutes/month - more than enough!

## 🤝 Contributing

Feel free to fork and improve this tracker!

## 📄 License

Open source - use freely!

---

**Live Dashboard:** `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/`

**Happy Tracking! 🎉**
