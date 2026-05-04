"""
State-specific configuration for multi-state election tracker.
Each state has its own parties, alliances, colors, ECI codes, and scraper settings.
"""

# ── Tamil Nadu ───────────────────────────────────────────────────────────────

TAMIL_NADU = {
    'name': 'Tamil Nadu',
    'code': 'tn',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
    'prev_year': 2021,
    'eci_state_code': 'S22',
    'total_pages': 12,  # 234 seats / ~20 per page
    'total_seats': 234,
    'shapefile_st_name': 'TAMIL NADU',
    'csv_file': 'election_results_tn.csv',
    'electors_file': 'electors_after_deletion_tn.csv',

    'parties': ['DMK', 'ADMK', 'BJP', 'IUML', 'INC', 'PMK', 'MDMK', 'VCK', 'CPI', 'CPIM', 'TMC(M)', 'NTK', 'AMMK', 'OTH', 'SDPI','KMDK','MMK','TVK','AWAITED'],

    'party_colors': {
        'DMK': '#FF0000',
        'ADMK': '#006400',
        'BJP': '#FF9900',
        'INC': '#1471C7',
        'PMK': "#989F03FF",
        'MDMK': '#8B0000',
        'VCK': '#0000FF',
        'CPI': "#FF78789E",     
        'CPIM': "#FF5757",
        'TMC(M)': "#FFC800",
        'NTK': '#800080',
        'AMMK': "#324501",
        'IUML': "#35FF02",
        'OTH': '#95A5A6',
        'SDPI': '#FF1493',
        'AWAITED': '#CCCCCC',
        'KMDK': '#00CED1',
        'MMK': "#2E0530",
        'TVK': "#E7DF01",
    },

    'alliances': {
        'DMK+': {
            'parties': ['DMK', 'INC', 'CPIM', 'CPI', 'VCK', 'MDMK','IUML','SDPI','KMDK','MMK'],
            'color': '#FF0000',
            'description': 'DMK, INC, CPIM, CPI, VCK, MDMK, IUML, SDPI, KMDK, MMK',
        },
        'ADMK+': {
            'parties': ['ADMK', 'BJP', 'PMK', 'TMC(M)', 'AMMK'],
            'color': '#006400',
            'description': 'ADMK, BJP, PMK, TMC(M), AMMK',
        },
        'TVK': {
            'parties': ['TVK'],
            'color': "#FFE120",
            'description': 'Tamilaga Vettri Kazhagam',
        },
        'OTH': {
            'parties': ['OTH', 'NTK'],
            'color': '#95A5A6',
            'description': 'Other Parties & Independents',
        },
    },

    'party_name_map': {
        'Dravida Munnetra Kazhagam': 'DMK',
        'All India Anna Dravida Munnetra Kazhagam': 'ADMK',
        'Bharatiya Janata Party': 'BJP',
        'Indian National Congress': 'INC',
        'Pattali Makkal Katchi': 'PMK',
        'Marumalarchi Dravida Munnetra Kazhagam': 'MDMK',
        'Viduthalai Chiruthaigal Katchi': 'VCK',
        'Communist Party of India': 'CPI',
        'Communist Party of India (Marxist)': 'CPIM',
        'Tamil Maanila Congress (Moopanar)': 'TMC(M)',
        'Naam Tamilar Katchi': 'NTK',
        'All India Anna Dravida Munnetra Kazhagam (Ammaa)': 'AMMK',
        'Indian Union Muslim League': 'IUML',
        'Social Democratic Party of India': 'SDPI',
        'Kongunadu Makkal Desia Katchi': 'KMDK', 
        'Manithaneya Makkal Katchi': 'MMK',
        'Tamilaga Vettri Kazhagam': 'TVK',
    },
}

# ── West Bengal ──────────────────────────────────────────────────────────────

WEST_BENGAL = {
    'name': 'West Bengal',
    'code': 'wb',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
    'prev_election_event': 'ResultAcGenMay2021',
    'prev_year': 2021,
    'eci_state_code': 'S25',
    'total_pages': 15,  # 294 seats / ~20 per page
    'total_seats': 294,
    'shapefile_st_name': 'WEST BENGAL',
    'csv_file': 'election_results_wb.csv',
    'electors_file': 'electors_after_deletion_wb.csv',

    'parties': ['TMC', 'BJP', 'INC', 'CPIM', 'RSP', 'AITC', 'ISF', 'BGPM','OTH', 'AWAITED'],

    'party_colors': {
        'TMC': "#23C000",
        'BJP': '#FF9900',
        'INC': '#1471C7',
        'CPIM': '#FF0000',
        'RSP': '#DC143C',
        'AITC': '#00BFFF',
        'ISF': "#014C01",
        'OTH': '#95A5A6',   
        'BGPM': '#800080',
        'AWAITED': '#CCCCCC',
    },

    'alliances': {
        'TMC': {
            'parties': ['TMC', 'BGPM'],
            'color': "#29B200",
            'description': 'All India Trinamool Congress and allies',
        },
        'NDA': {
            'parties': ['BJP'],
            'color': '#FF9900',
            'description': 'Bharatiya Janata Party',
        },
        'INC': {
            'parties': ['INC'],
            'color': '#1471C7',
            'description': 'Indian National Congress',
        },
        'LEFT': {
            'parties': ['CPIM', 'RSP'],
            'color': '#FF0000',
            'description': 'CPIM, RSP',
        },
        'OTH': {
            'parties': ['ISF', 'OTH'],
            'color': '#95A5A6',
            'description': 'Other Parties & Independents',
        },
    },

    'party_name_map': {
        'All India Trinamool Congress': 'TMC',
        'Bharatiya Janata Party': 'BJP',
        'Indian National Congress': 'INC',
        'Communist Party of India (Marxist)': 'CPIM',
        'Revolutionary Socialist Party': 'RSP',
        'Indian Secular Front': 'ISF',
        'Bharatiya Gorkha Prajatantrik Morcha': 'BGPM',
    },
}

# ── Assam ────────────────────────────────────────────────────────────────────

ASSAM = {
    'name': 'Assam',
    'code': 'assam',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
    'prev_election_event': 'ResultAcGenMay2021',
    'prev_year': 2021,
    'eci_state_code': 'S03',
    'total_pages': 7,  # 126 seats / ~20 per page
    'total_seats': 126,
    'shapefile_st_name': 'ASSAM',
    'csv_file': 'election_results_assam.csv',
    'electors_file': 'electors_after_deletion_assam.csv',

    'parties': ['BJP', 'AGP', 'UPPL', 'INC', 'AIUDF', 'BPF', 'CPI', 'CPIM', 'AJP', 'OTH', 'AWAITED'],

    'party_colors': {
        'BJP': '#FF9900',
        'AGP': '#FFD700',
        'UPPL': '#8B4513',
        'INC': '#1471C7',
        'AIUDF': '#006400',
        'BPF': '#800000',
        'CPI': '#FF0000',
        'CPIM': '#CC0000',
        'AJP': '#4169E1',
        'OTH': '#95A5A6',
        'AWAITED': '#CCCCCC',
        'RD': "#EE5D44",
    },

    'alliances': {
        'NDA': {
            'parties': ['BJP', 'AGP', 'BPF'],
            'color': '#FF9900',
            'description': 'BJP, AGP, BPF',
        },
        'UPA': {
            'parties': ['INC', 'CPI', 'CPIM', 'AJP'],
            'color': '#1471C7',
            'description': 'INC, CPI, CPIM, AJP',
        },
        'OTH': {
            'parties': ['OTH', 'AIUDF', 'UPPL'],
            'color': '#95A5A6',
            'description': 'Other Parties & Independents',
        },
    },

    'party_name_map': {
        'Bharatiya Janata Party': 'BJP',
        'Asom Gana Parishad': 'AGP',
        'United Peoples Party Liberal': 'UPPL',
        'Indian National Congress': 'INC',
        'All India United Democratic Front': 'AIUDF',
        'Bodoland Peoples Front': 'BPF',
        'Communist Party of India': 'CPI',
        'Communist Party of India (Marxist)': 'CPIM',
        'Assam Jatiya Parishad': 'AJP',
        'Raijor Dal': 'RD',
    },
}

# ── Kerala ───────────────────────────────────────────────────────────────────

KERALA = {
    'name': 'Kerala',
    'code': 'kerala',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
    'prev_election_event': 'ResultAcGenMay2021',
    'prev_year': 2021,
    'eci_state_code': 'S11',
    'total_pages': 8,  # 140 seats / ~20 per page
    'total_seats': 140,
    'shapefile_st_name': 'KERALA',
    'csv_file': 'election_results_kerala.csv',
    'electors_file': 'electors_after_deletion_kerala.csv',

    'parties': ['CPI(M)', 'CPI', 'INC', 'RJD', 'IUML', 'KC(M)', 'NCP', 'BJP', 'RSP', 'JD(S)', 'KC', 'OTH', 'ISJD', 'AWAITED'],

    'party_colors': {
        'CPI(M)': '#FF0000',
        'CPI': '#CC0000',
        'INC': '#1471C7',
        'IUML': '#006400',
        'KC(M)': '#FFD700',
        'NCP': '#00BFFF',
        'BJP': '#FF9900',
        'RSP(L)': '#DC143C',
        'JD(S)': '#228B22',
        'KC': '#8B008B',
        'OTH': '#95A5A6',
        'AWAITED': '#CCCCCC',
        'RJD': "#0C6249",   
        'ISJD'  : "#800000",
        'KC' : "#880048",
        'RSP': "#FF6347",
    },

    'alliances': {
        'LDF': {
            'parties': ['CPI(M)', 'CPI', 'RSP(L)', 'JD(S)', 'KC', 'NCP', 'RJD', 'KC(M)', 'ISJD'],
            'color': '#FF0000',
            'description': 'CPI(M), CPI, RSP(L), JD(S), KEC, NCP, RJD, KC(M), ISJD',
        },
        'UDF': {
            'parties': ['INC', 'IUML','RSP'],
            'color': '#1471C7',
            'description': 'INC, IUML, RSP',
        },
        'NDA': {
            'parties': ['BJP'],
            'color': '#FF9900',
            'description': 'Bharatiya Janata Party',
        },
        'OTH': {
            'parties': ['OTH','KC'],
            'color': '#95A5A6',
            'description': 'KC, Other Parties & Independents',
        },
    },

    'party_name_map': {
        'Communist Party of India (Marxist)': 'CPI(M)',
        'Communist Party of India': 'CPI',
        'Indian National Congress': 'INC',
        'Indian Union Muslim League': 'IUML',
        'Kerala Congress (M)': 'KC(M)',
        'Nationalist Congress Party': 'NCP',
        'Bharatiya Janata Party': 'BJP',
        'Revolutionary Socialist Party': 'RSP',
        'Janata Dal (Secular)': 'JD(S)',
        'Kerala Congress': 'KC',
        'Rashtriya Janata Dal': 'RJD',
        'Indian Socialist Janata Dal': 'ISJD',
        'Revolutionary Socialist Party (Leninist)': 'RSP(L)',
        'Kerala Congress (Jacob)': 'KC(M)',
    },
}

# ── Puducherry ───────────────────────────────────────────────────────────────

PUDUCHERRY = {
    'name': 'Puducherry',
    'code': 'puducherry',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
    'prev_election_event': 'ResultAcGenMay2021',
    'prev_year': 2021,
    'eci_state_code': 'U07',  # Union Territory
    'total_pages': 2,  # 30 seats / ~20 per page
    'total_seats': 30,
    'shapefile_st_name': 'PUDUCHERRY',
    'csv_file': 'election_results_puducherry.csv',
    'electors_file': 'electors_after_deletion_puducherry.csv',

    'parties': ['BJP', 'INC', 'DMK', 'AINRC', 'ADMK', 'NR', 'OTH','TVK', 'AWAITED'],

    'party_colors': {
        'BJP': '#FF9900',
        'INC': '#1471C7',
        'DMK': '#FF0000',
        'AINRC': '#006400',
        'ADMK': '#228B22',
        'NR': '#800080',
        'TVK': '#E7DF01',
        'OTH': '#95A5A6',
        'AWAITED': '#CCCCCC',
    },

    'alliances': {
        'NDA': {
            'parties': ['BJP', 'AINRC', 'ADMK'],
            'color': '#FF9900',
            'description': 'BJP, AINRC, ADMK',
        },
        'UPA': {
            'parties': ['INC', 'DMK'],
            'color': '#1471C7',
            'description': 'INC, DMK',
        },
        'TVK': {
            'parties': ['TVK'], 
            'color': '#E7DF01',
            'description': 'Tamilaga Vettri Kazhagam',
        },
        'OTH': {
            'parties': ['NR', 'OTH'],
            'color': '#95A5A6',
            'description': 'Other Parties & Independents',
        },
    },

    'party_name_map': {
        'Bharatiya Janata Party': 'BJP',
        'Indian National Congress': 'INC',
        'Dravida Munnetra Kazhagam': 'DMK',
        'All India N.R. Congress': 'AINRC',
        'All India Anna Dravida Munnetra Kazhagam': 'ADMK',
        'Tamilaga Vettri Kazhagam': 'TVK',
    },

    # Default view: zoom into Puducherry town (20+ seats in a ~35km box).
    # Users can scroll out to see Karaikal (5 seats, ~130km south),
    # Mahe (1 seat, far west) and Yanam (1 seat, far NE).
    # Coordinates are Web Mercator (EPSG:3857).
    'map_default_bounds': {
        'x': (8858000, 8898000),
        'y': (1318000, 1358000),
    },
}


# ── Bihar (TEST — real Nov 2025 results, used for pipeline speed testing) ────

BIHAR = {
    'name': 'Bihar',
    'code': 'bihar',
    'year': 2025,
    'election_event': 'ResultAcGenNov2025',
    'prev_election_event': 'ResultAcGenNov2020',
    'prev_year': 2020,
    'eci_state_code': 'S04',
    'total_pages': 13,   # 243 seats / ~20 per page
    'total_seats': 243,
    'shapefile_st_name': 'BIHAR',
    'csv_file': 'election_results_bihar.csv',
    'electors_file': 'electors_after_deletion_bihar.csv',  # not present — votes_pct defaults to 100

    'parties': ['JDU', 'BJP', 'RJD', 'INC', 'CPIM-L', 'HAM', 'BSP', 'OTH', 'AWAITED'],

    'party_colors': {
        'JDU':    '#1E8449',
        'BJP':    '#FF9900',
        'RJD':    '#FF0000',
        'INC':    '#1471C7',
        'CPIM-L': '#CC0000',
        'HAM':    '#8B0000',
        'BSP':    '#0000FF',
        'OTH':    '#95A5A6',
        'AWAITED': '#CCCCCC',
    },

    'alliances': {
        'NDA': {
            'parties': ['JDU', 'BJP', 'HAM'],
            'color': '#FF9900',
            'description': 'JDU, BJP, HAM',
        },
        'Mahagathbandhan': {
            'parties': ['RJD', 'INC', 'CPIM-L'],
            'color': '#FF0000',
            'description': 'RJD, INC, CPI(ML)',
        },
        'OTH': {
            'parties': ['BSP', 'OTH'],
            'color': '#95A5A6',
            'description': 'Other Parties & Independents',
        },
    },

    'party_name_map': {
        'Janata Dal (United)':                    'JDU',
        'Bharatiya Janata Party':                 'BJP',
        'Rashtriya Janata Dal':                   'RJD',
        'Indian National Congress':               'INC',
        'Communist Party of India (Marxist-Leninist) (Liberation)': 'CPIM-L',
        'Hindustani Awam Morcha (Secular)':       'HAM',
        'Bahujan Samaj Party':                    'BSP',
    },
}


# ── Registry ─────────────────────────────────────────────────────────────────

ALL_STATES = {
    'tn': TAMIL_NADU,
    'wb': WEST_BENGAL,
    'assam': ASSAM,
    'kerala': KERALA,
    'puducherry': PUDUCHERRY,
    # 'bihar': BIHAR,   # hidden from nav
}

DEFAULT_STATE = 'tn'


def get_state_config(state_code):
    """Get config for a state by its short code (e.g. 'tn', 'wb', 'assam')"""
    return ALL_STATES.get(state_code.lower())


def get_party_to_alliance(state_config):
    """Build party → alliance mapping from state config"""
    mapping = {}
    for alliance_name, alliance_info in state_config['alliances'].items():
        for party in alliance_info['parties']:
            mapping[party] = alliance_name
    mapping['AWAITED'] = 'AWAITED'
    return mapping


def get_alliance_colors(state_config):
    """Build alliance → color mapping from state config"""
    colors = {}
    for alliance_name, alliance_info in state_config['alliances'].items():
        colors[alliance_name] = alliance_info['color']
    colors['AWAITED'] = '#CCCCCC'
    return colors


def normalize_party_name(party_name, state_config):
    """Convert full party name to short code using state-specific mapping"""
    if not party_name or str(party_name) == 'nan':
        return 'OTH'

    party_name = str(party_name).strip()

    # Direct match in state-specific map
    if party_name in state_config['party_name_map']:
        return state_config['party_name_map'][party_name]

    # Check if already a short code in this state's party list
    if party_name in state_config['parties']:
        return party_name

    # Common fallbacks
    upper = party_name.upper()
    if 'INDEPENDENT' in upper or upper == 'IND':
        return 'OTH'
    if 'NOTA' in upper or 'NONE OF THE ABOVE' in upper:
        return 'OTH'

    # Partial match against the state's party_name_map values
    for full_name, code in state_config['party_name_map'].items():
        if full_name.upper() in upper or upper in full_name.upper():
            return code

    return 'OTH'
