# 🚀 Tomorrow's Action Plan - Election Day

## When Results Go Live:

### Step 1: Check Live Data Structure (5 mins)
```bash
# Manually trigger GitHub Actions OR run locally:
python scraper.py

# Check what data we got:
python transform_data.py preview
```

### Step 2: Adjust Scraper (10 mins)
Based on what you see, modify `scraper.py`:
- [ ] Update `indices_of_interest` to get all needed columns
- [ ] Add candidate name extraction if available
- [ ] Add votes counted percentage if available
- [ ] Test locally: `python scraper.py`

### Step 3: Update Transformation (5 mins)
Modify `transform_data.py`:
- [ ] Update column mappings to match actual seat.csv structure
- [ ] Fix constituency name → AC_NO mapping
- [ ] Test: `python transform_data.py`

### Step 4: Update Shapefile (2 mins)
```bash
python merge_data.py
```

### Step 5: Test Map (2 mins)
```bash
python map_app.py
# Open http://localhost:5000
```

### Step 6: Deploy Updates (5 mins)
```bash
git add .
git commit -m "Update with live election data"
git push
```

---

## 🔧 Quick Reference Commands

### Preview current data structure:
```bash
python transform_data.py preview
```

### Full pipeline (after adjustments):
```bash
python scraper.py           # Get latest data
python transform_data.py    # Transform to CSV
python merge_data.py        # Update shapefile
python map_app.py          # Test locally
```

### Check scraper logs on GitHub:
- Go to: https://github.com/abhi0420/election-tracker/actions
- Click latest workflow run
- Check logs for errors

---

## 📋 Things to Check Tomorrow:

1. **Website structure:**
   - [ ] Are candidate names available?
   - [ ] Is votes counted % available?
   - [ ] What are the exact column headers?

2. **Constituency mapping:**
   - [ ] Do constituency names match shapefile AC_NAME?
   - [ ] Is there a number in the constituency name?
   - [ ] Do we need manual mapping?

3. **Data updates:**
   - [ ] How often does ECI update? (every 5 mins enough?)
   - [ ] Are results cumulative or final?

---

## 🆘 If Something Breaks:

### Scraper fails:
```bash
# Check GitHub Actions logs
# OR run locally with: python scraper.py
# Check error message and adjust selectors
```

### Transformation fails:
```bash
# Check seat.csv structure: head seat.csv
# Adjust transform_data.py mappings
# Test: python transform_data.py preview
```

### Map not showing data:
```bash
# Check if election_results.csv updated
# Check if merge_data.py ran successfully
# Restart Flask: python map_app.py
```

---

## 💡 Pro Tips:

- **Keep old files as backup** before overwriting
- **Test with small sample first** (few constituencies)
- **Check GitHub Actions logs** every 10 mins to ensure scraper is working
- **Have this plan open** on election day for quick reference

---

**Good luck tomorrow! 🎉**
