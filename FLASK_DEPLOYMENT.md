# 🚀 Deploy Flask Map App to Render

## Step-by-Step Guide

### 1. Push Files to GitHub

```bash
git add .
git commit -m "Prepare Flask app for production deployment"
git push
```

### 2. Deploy to Render

1. **Go to:** https://render.com/
2. **Sign up** with your GitHub account
3. **Click "New +"** → **"Web Service"**
4. **Connect Repository:**
   - Find and select `election-tracker`
   - Click "Connect"

5. **Configure Settings:**
   - **Name:** `bihar-election-tracker` (or your choice)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements-flask.txt`
   - **Start Command:** `gunicorn map_app:app --bind 0.0.0.0:$PORT`
   - **Plan:** Free

6. **Click "Create Web Service"**

### 3. Wait for Deployment (5-10 mins)

Render will:
- Install dependencies
- Build your app
- Start the server

### 4. Access Your App

Your map will be live at: `https://bihar-election-tracker.onrender.com/`

---

## ⚠️ Important Notes:

### **Shapefile Upload:**
Your `ac/` folder with shapefiles needs to be in the repo. Make sure it's committed:

```bash
git add ac/
git commit -m "Add shapefiles"
git push
```

### **Free Tier Limitations:**
- App will spin down after 15 mins of inactivity
- First request after sleep takes ~30 seconds
- 750 hours/month free

### **If Deployment Fails:**

1. **Check Logs:** Click on your service → "Logs" tab
2. **Common Issues:**
   - Missing shapefile → Make sure `ac/` folder is in repo
   - Missing dependencies → Check `requirements-flask.txt`
   - Port issues → Handled by our PORT config

---

## 🔧 Alternative: Railway (Backup Option)

If Render doesn't work:

1. Go to https://railway.app/
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select `election-tracker`
5. Railway auto-detects Flask and deploys!

---

## 📊 Post-Deployment:

### Update Your Workflow

Once deployed, you can:
1. Access your map at the Render URL
2. It will automatically show updated data from `election_results.csv`
3. Every time you push to GitHub, Render auto-deploys

### Connect to Live Data

To show live election results on your map:
1. Tomorrow when live: Run the data transformation pipeline
2. Push updated `election_results.csv` to GitHub
3. Run `merge_data.py` to update shapefile
4. Push updated shapefile to GitHub
5. Render will auto-redeploy with new data!

---

## 🎉 That's It!

Your interactive election map will be live and accessible to anyone!
