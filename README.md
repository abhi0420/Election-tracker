# Bihar Election Tracker 2025 🗳️# 🗳️ Live Election Results Tracker



Live interactive election results tracker for Bihar Assembly Elections 2025, built with Flask, Selenium, and Bokeh.Automated election results tracker that scrapes data every 5 minutes and provides a live web dashboard.



## 🎯 Features## 🚀 Features



- **Live Data Scraping**: Automatically scrapes all 243 constituencies from ECI website every 5 minutes- ✅ Automated scraping every 5 minutes via GitHub Actions

- **Interactive Map**: Clickable constituency map with detailed candidate information- ✅ Generates both CSV and JSON outputs

- **Real-time Updates**: GitHub Actions workflow updates data automatically- ✅ Live web dashboard with auto-refresh

- **Mobile Responsive**: Fully accessible on phones with optimized layout- ✅ Completely free hosting using GitHub

- **Advanced Filtering**: Filter by Parliament Seat, District, Party, or Lead Margin- ✅ No server maintenance required

- **Party Breakdowns**: Detailed alliance and party-wise seat distribution

- **Vote Tracking**: Shows votes counted percentage per constituency## 📋 Setup Instructions



## 📊 Final Results (November 23, 2025)### Step 1: Create GitHub Repository



- **NDA**: 201 seats (BJP 96, JDU 85, LJP 19, HAM 5, RLM 4)1. Go to [GitHub](https://github.com) and create a new repository

- **MGB**: 36 seats (RJD 24, INC 2, CPIM 2)2. Name it something like `election-tracker`

- **AIMIM**: 5 seats3. Make it **Private** (keeps your data secure)

- **Others**: 1 seat4. Initialize with a README (optional)



**Total**: 243 constituencies### Step 2: Push Your Code



## 🚀 Tech StackOpen terminal in your project folder and run:



- **Backend**: Flask 3.0.0```bash

- **Scraping**: Selenium 4.15.2 with Chrome WebDrivergit init

- **Mapping**: Bokeh 3.3.0 with GeoPandasgit add .

- **Automation**: GitHub Actions (cron: every 5 minutes)git commit -m "Initial commit"

- **Deployment**: Render (auto-deploy from main branch)git branch -M main

- **Data Storage**: CSV/JSON files in Gitgit remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git

git push -u origin main

## 📁 Project Structure```



```Replace `YOUR-USERNAME` and `YOUR-REPO-NAME` with your actual GitHub username and repository name.

Tracker/

├── scraper.py              # Main scraper (243 constituencies, 8 workers)### Step 3: Enable GitHub Actions

├── map_app.py              # Flask app with interactive Bokeh map

├── .github/workflows/      1. Go to your repository on GitHub

│   └── scraper.yml         # GitHub Actions automation2. Click the **Actions** tab

├── ac/                     # Shapefiles for Bihar constituencies3. If prompted, click "I understand my workflows, go ahead and enable them"

├── election_results.csv    # Latest election data4. The workflow will start running automatically every 5 minutes

├── electors_after_deletion.csv  # Voter count per constituency

├── requirements.txt        # Python dependenciesYou can also manually trigger it:

└── README.md              # This file- Go to **Actions** tab

```- Click **Election Data Scraper** workflow

- Click **Run workflow** button

## 🛠️ Setup & Installation

### Step 4: Create GitHub Personal Access Token (for private repo access)

### Prerequisites

- Python 3.11+1. Go to GitHub **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**

- Chrome/Chromium browser2. Click **Generate new token (classic)**

- Git3. Name it "Election Tracker Access"

4. Select expiration (recommend "No expiration" for continuous access)

### Local Development5. Check **only** the `repo` scope (Full control of private repositories)

6. Click **Generate token**

1. **Clone the repository**7. **COPY THE TOKEN** - you won't see it again!

   ```bash

   git clone https://github.com/abhi0420/Election-tracker.git### Step 5: Host Your Dashboard

   cd Election-tracker

   ```**Option A: Local Hosting (Recommended)**

- Simply open `index.html` in your browser

2. **Create virtual environment**- Data stays private on your machine

   ```bash- Free and secure

   python -m venv .venv

   .venv\Scripts\activate  # Windows**Option B: Private Web Host**

   # source .venv/bin/activate  # Linux/Mac- Deploy to Vercel/Netlify with password protection

   ```- Update `index.html` to use authenticated GitHub API:



3. **Install dependencies**```javascript

   ```bashconst DATA_URL = 'https://api.github.com/repos/YOUR-USERNAME/YOUR-REPO/contents/seat.json';

   pip install -r requirements.txtconst TOKEN = 'YOUR_GITHUB_TOKEN'; // From Step 4

   ```

async function fetchElectionData() {

4. **Run the scraper** (optional - data already in repo)    const response = await fetch(DATA_URL, {

   ```bash        headers: {

   python scraper.py            'Authorization': `token ${TOKEN}`,

   ```            'Accept': 'application/vnd.github.v3.raw'

        }

5. **Start Flask app**    });

   ```bash    // ... rest of code

   python map_app.py}

   ``````



6. **Open browser****Option C: Deploy to Private Server**

   ```- Use any hosting platform you control

   http://localhost:5000- Configure authentication/password protection

   ```- Point to your GitHub repo with token authentication



## 🤖 Automated Scraping## 📁 Project Structure



GitHub Actions runs `scraper.py` every 5 minutes and commits updated data:```

election-tracker/

- **Schedule**: `*/5 * * * *` (every 5 minutes)├── .github/

- **Concurrency control**: Prevents parallel runs│   └── workflows/

- **Git push retry**: Handles conflicts automatically│       └── scraper.yml          # GitHub Actions workflow (runs every 5 mins)

- **Files updated**: `election_results.csv`, `seat.csv`, `election_results.json`├── scraper.py                    # Main scraper script

├── requirements.txt              # Python dependencies

## 🗺️ Data Sources├── index.html                    # Live dashboard webpage

├── seat.csv                      # Output CSV (auto-generated)

- **Election Data**: Election Commission of India (ECI)└── seat.json                     # Output JSON (auto-generated)

  - URL: https://results.eci.gov.in/ResultAcGenNov2025/```

- **Shapefiles**: Bihar Assembly Constituency boundaries

- **Voter Data**: `electors_after_deletion.csv` (total votes cast per AC)## 🔧 How It Works



## 🎨 Party Color Codes1. **GitHub Actions** runs `scraper.py` every 5 minutes

2. Script scrapes election data from ECI website

| Party/Alliance | Color Code | Hex |3. Generates `seat.csv` and `seat.json` files

|---------------|-----------|-----|4. GitHub Actions commits the updated files back to the repo

| BJP | Orange | `#FF9900` |5. **GitHub Pages** serves the `index.html` dashboard

| JDU | Dark Blue | `#190061` |6. Dashboard fetches latest `seat.json` every 60 seconds

| LJP | Yellow | `#FFF300` |

| HAM | Purple | `#4C007A` |## 💾 Data Format

| RLM | Violet | `#8B4789` |

| RJD | Dark Green | `#006400` |### JSON Structure

| INC | Blue | `#1471C7` |```json

| CPIM | Red | `#FF0000` |{

| AIMIM | Green | `#009C1D` |  "last_updated": "2025-11-13T10:30:00Z",

| Others | Gray | `#95A5A6` |  "total_seats": 90,

  "data": [

## 📱 Mobile Support    {

      "Seat": "Constituency Name",

The tracker includes JavaScript-based mobile responsiveness:      "Leading": "Party A",

- Filters appear above map on phones (≤768px width)      "Trailing": "Party B",

- Full-width layout for better accessibility      "3rd Place": "Party C",

- Touch-friendly constituency selection      "1": 50000,

      "2": 45000,

## 🐛 Known Issues & Fixes      "3": 30000,

      "Rest": 15000

### Fixed Issues    }

- ✅ AC_NO data mismatch (off-by-one error) - Fixed by preserving AC_NO column  ]

- ✅ Vote percentage >100% - Capped at 100% in display and scraper}

- ✅ AIMIM/RLM not detected - Fixed PARTY_NAME_MAP dictionary```

- ✅ Mobile layout issues - Added responsive JavaScript reorganization

### CSV Format

## 🔧 Configuration```csv

Seat,Leading,Trailing,3rd Place,1,2,3,Rest

### Scraper SettingsConstituency Name,Party A,Party B,Party C,50000,45000,30000,15000

- **Workers**: 8 concurrent threads```

- **Retries**: 3 attempts per constituency

- **Timeout**: 30 seconds per page load## 🎨 Customization

- **Total constituencies**: 243

### Change Scraping Interval

### Flask Settings

- **Host**: `0.0.0.0`Edit `.github/workflows/scraper.yml`:

- **Port**: 5000 (or `PORT` env variable)```yaml

- **Debug**: `False` (production)schedule:

  - cron: '*/5 * * * *'  # Every 5 minutes

## 📈 Performance  # - cron: '*/10 * * * *'  # Every 10 minutes

  # - cron: '0 * * * *'     # Every hour

- **Scraping time**: ~5-7 minutes for all 243 seats```

- **Page load**: <2 seconds (with cached shapefile)

- **Mobile responsive**: <768px breakpoint### Change Dashboard Refresh Rate

- **Total requests served**: ~147 requests during election day

Edit `index.html`:

## 🚀 Deployment (Render)```javascript

let countdown = 60; // Refresh every 60 seconds

The app is deployed on Render with auto-deploy enabled:```



1. **Live URL**: https://bihar-election-tracker.onrender.com### Styling

2. **Auto-deploy**: Triggered on push to `main` branch

3. **Build command**: `pip install -r requirements.txt`All styles are in `index.html` inside the `<style>` tag. Modify colors, fonts, layout as needed.

4. **Start command**: `python map_app.py`

5. **Environment**: Python 3.11## 🐛 Troubleshooting



## 🔮 Future Improvements### Actions Failing?

- Check the **Actions** tab for error logs

- Multi-state support (TN, Kerala, WB, Assam, Mizoram for 2026 elections)- Ensure repository is **Public**

- Dynamic state selection- Verify all files are committed properly

- Historical election comparison

- Export to PDF/Image### Dashboard Not Loading Data?

- Real-time WebSocket updates- Check browser console for errors (F12)

- Candidate-level statistics- Verify the `DATA_URL` points to correct GitHub raw URL

- Make sure `seat.json` exists in your repository

## 📝 License

### Scraper Errors?

This project is built for educational and informational purposes. Election data belongs to the Election Commission of India.- Website structure might have changed

- Check Chrome driver compatibility

## 🙏 Acknowledgments- Review logs in GitHub Actions



- Election Commission of India for providing live election data## 📊 Monitoring

- Bihar Assembly Constituency shapefiles

- Bokeh for amazing mapping capabilities- View workflow runs: **Actions** tab

- GitHub Actions for free CI/CD- Check scraper logs: Click on any workflow run

- See commit history: **Commits** section

---

## 💰 Cost

**Note**: This tracker was live during the election counting day (November 23, 2025) and continues to serve as a historical record of the election results.

**100% FREE** 

**Built with ❤️ for Bihar Elections 2025**- GitHub Actions: 2000 minutes/month for **private repos** (Free tier)

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
