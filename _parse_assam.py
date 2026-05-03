import pdfplumber, re, pandas as pd

all_lines = []
with pdfplumber.open('assam.pdf') as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            for line in text.split('\n'):
                all_lines.append(line.strip())
all_lines = [l for l in all_lines if l]

def last_big_number(line):
    """Return last number with 5+ digits on the line, or None."""
    nums = re.findall(r'[\d,]+', line)
    for n in reversed(nums):
        val = int(n.replace(',', ''))
        if 50000 <= val <= 500000:
            return val
    return None

rows = {}  # AC_NO -> Total_Electors

for i, line in enumerate(all_lines):

    # Pattern A: district-change line: serial DISTRICT ac_no NAME ... TOTAL
    # e.g. "1 Kokrajhar 1 Gossaigaon 154 154 57754 57258 2 115014"
    # e.g. "21 Lakhimpur 73 Bihpuria 206 206 83095 83631 0 166726"
    m_dist = re.match(r'^(\d{1,3})\s+[A-Z][A-Za-z0-9\s\.]+?\s+(\d{1,3})\s+[A-Z]', line)
    if m_dist:
        ac_no = int(m_dist.group(2))
        total = last_big_number(line)
        if 1 <= ac_no <= 126 and total:
            rows[ac_no] = total
            continue

    # Pattern B: district-continuation or simple line: ac_no NAME ... TOTAL
    # e.g. "2 Dotma (ST) 146 146 53653 54270 0 107923"
    m_cont = re.match(r'^(\d{1,3})\s+[A-Z]', line)
    if m_cont:
        ac_no = int(m_cont.group(1))
        total = last_big_number(line)
        if 1 <= ac_no <= 126 and total:
            rows[ac_no] = total
            continue

    # Pattern C: district-name continuation prefix, then ac_no NAME ... TOTAL
    # e.g. "Anglong 112 Amri (ST) 165 165 50291 50540 0 100831"
    m_pfx = re.match(r'^[A-Z][A-Za-z\s\.]+?\s+(\d{1,3})\s+[A-Z]', line)
    if m_pfx:
        ac_no = int(m_pfx.group(1))
        total = last_big_number(line)
        if 1 <= ac_no <= 126 and total:
            rows[ac_no] = total
            continue

    # Pattern E: all-digits line starting with valid AC_NO, previous line is a name fragment
    # e.g. prev="Ram Krishna Nagar", line="126 277 277 111223 106274 3 217500", next="(SC)"
    if re.match(r'^[\d\s]+$', line):
        m_e = re.match(r'^(\d{1,3})\s', line)
        if m_e:
            first = int(m_e.group(1))
            total = last_big_number(line)
            prev = all_lines[i-1] if i > 0 else ''
            if (1 <= first <= 126 and total and first not in rows and
                    re.match(r'^[A-Za-z\s\(\)\-]+$', prev)):
                rows[first] = total
                continue

    # Pattern D: numbers-only line; AC_NO is on the NEXT line (alone)
    # e.g. line="270 270 108302 107208 0 215510", next="8 Bajali 21 Sorbhog" -> AC_NO=21
    # e.g. line="241 241 97282 99178 0 196460", next="28" -> AC_NO=28
    # e.g. line="339 339 145645 132717 2 278364", next="122" -> AC_NO=122
    if re.match(r'^[\d\s]+$', line):
        total = last_big_number(line)
        if total:
            # Look at next 1-2 lines for an AC_NO
            for j in range(i+1, min(i+3, len(all_lines))):
                nxt = all_lines[j]
                # Next line is just a number (AC_NO alone)
                m_alone = re.match(r'^(\d{1,3})\s*$', nxt)
                if m_alone:
                    ac_no = int(m_alone.group(1))
                    if 1 <= ac_no <= 126:
                        rows[ac_no] = total
                        break
                # Next line starts with "SERIAL DISTRICT AC_NO NAME" pattern
                m_next_dist = re.match(r'^\d{1,3}\s+[A-Z][A-Za-z\s]+?\s+(\d{1,3})\s+[A-Z]', nxt)
                if m_next_dist:
                    ac_no = int(m_next_dist.group(1))
                    if 1 <= ac_no <= 126:
                        rows[ac_no] = total
                        break

df = pd.DataFrame([{'AC_NO': k, 'Total_Electors': v} for k, v in rows.items()])
df = df.sort_values('AC_NO').reset_index(drop=True)
print(f'Extracted {len(df)} constituencies')
missing = set(range(1, 127)) - set(df['AC_NO'])
print(f'Missing: {sorted(missing)}')

template = pd.read_csv('electors_after_deletion_assam.csv')
merged = template[['AC_NO','AC_NAME','Turnout_Pct']].merge(df, on='AC_NO', how='left')
merged = merged[['AC_NO','AC_NAME','Total_Electors','Turnout_Pct']]
merged.to_csv('electors_after_deletion_assam_new.csv', index=False)
print(f'Saved {len(merged)} rows, {merged["Total_Electors"].notna().sum()} with electors data')
