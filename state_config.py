"""
State-specific configuration for multi-state election tracker.
Each state has its own parties, alliances, colors, ECI codes, and scraper settings.
"""

# ── Tamil Nadu ───────────────────────────────────────────────────────────────

TAMIL_NADU = {
    'name': 'Tamil Nadu',
    'code': 'tn',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',  # placeholder – update when ECI publishes
    'eci_state_code': 'S23',
    'total_pages': 12,  # 234 seats / ~20 per page
    'total_seats': 234,
    'shapefile_st_name': 'TAMIL NADU',
    'csv_file': 'election_results_tn.csv',
    'electors_file': 'electors_after_deletion_tn.csv',

    'parties': ['DMK', 'ADMK', 'BJP', 'INC', 'PMK', 'MDMK', 'VCK', 'CPI', 'CPIM', 'TMC(M)', 'NTK', 'AMMK', 'OTH', 'AWAITED'],

    'party_colors': {
        'DMK': '#FF0000',
        'ADMK': '#006400',
        'BJP': '#FF9900',
        'INC': '#1471C7',
        'PMK': '#FFFF00',
        'MDMK': '#8B0000',
        'VCK': '#0000FF',
        'CPI': '#FF0000',
        'CPIM': '#CC0000',
        'TMC(M)': '#FFD700',
        'NTK': '#800080',
        'AMMK': '#228B22',
        'OTH': '#95A5A6',
        'AWAITED': '#CCCCCC',
    },

    'alliances': {
        'DMK+': {
            'parties': ['DMK', 'INC', 'CPIM', 'CPI', 'VCK', 'MDMK'],
            'color': '#FF0000',
            'description': 'DMK, INC, CPIM, CPI, VCK, MDMK',
        },
        'ADMK+': {
            'parties': ['ADMK', 'BJP', 'PMK', 'TMC(M)'],
            'color': '#006400',
            'description': 'ADMK, BJP, PMK, TMC(M)',
        },
        'NTK': {
            'parties': ['NTK'],
            'color': '#800080',
            'description': 'Naam Tamilar Katchi',
        },
        'OTH': {
            'parties': ['OTH', 'AMMK'],
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
    },
}

# ── West Bengal ──────────────────────────────────────────────────────────────

WEST_BENGAL = {
    'name': 'West Bengal',
    'code': 'wb',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
    'eci_state_code': 'S28',
    'total_pages': 15,  # 294 seats / ~20 per page
    'total_seats': 294,
    'shapefile_st_name': 'WEST BENGAL',
    'csv_file': 'election_results_wb.csv',
    'electors_file': 'electors_after_deletion_wb.csv',

    'parties': ['TMC', 'BJP', 'INC', 'CPIM', 'RSP', 'AITC', 'ISF', 'OTH', 'AWAITED'],

    'party_colors': {
        'TMC': '#00BFFF',
        'BJP': '#FF9900',
        'INC': '#1471C7',
        'CPIM': '#FF0000',
        'RSP': '#DC143C',
        'AITC': '#00BFFF',
        'ISF': '#006400',
        'OTH': '#95A5A6',
        'AWAITED': '#CCCCCC',
    },

    'alliances': {
        'TMC': {
            'parties': ['TMC', 'AITC'],
            'color': '#00BFFF',
            'description': 'All India Trinamool Congress',
        },
        'NDA': {
            'parties': ['BJP'],
            'color': '#FF9900',
            'description': 'Bharatiya Janata Party',
        },
        'INDIA': {
            'parties': ['INC', 'CPIM', 'RSP'],
            'color': '#1471C7',
            'description': 'INC, CPIM, RSP',
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
    },
}

# ── Assam ────────────────────────────────────────────────────────────────────

ASSAM = {
    'name': 'Assam',
    'code': 'assam',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
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
    },

    'alliances': {
        'NDA': {
            'parties': ['BJP', 'AGP', 'UPPL'],
            'color': '#FF9900',
            'description': 'BJP, AGP, UPPL',
        },
        'UPA': {
            'parties': ['INC', 'AIUDF', 'BPF', 'CPI', 'CPIM', 'AJP'],
            'color': '#1471C7',
            'description': 'INC, AIUDF, BPF, CPI, CPIM, AJP',
        },
        'OTH': {
            'parties': ['OTH'],
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
    },
}

# ── Kerala ───────────────────────────────────────────────────────────────────

KERALA = {
    'name': 'Kerala',
    'code': 'kerala',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
    'eci_state_code': 'S12',
    'total_pages': 8,  # 140 seats / ~20 per page
    'total_seats': 140,
    'shapefile_st_name': 'KERALA',
    'csv_file': 'election_results_kerala.csv',
    'electors_file': 'electors_after_deletion_kerala.csv',

    'parties': ['CPIM', 'CPI', 'INC', 'IUML', 'KC(M)', 'NCP', 'BJP', 'RSP', 'JD(S)', 'KEC', 'OTH', 'AWAITED'],

    'party_colors': {
        'CPIM': '#FF0000',
        'CPI': '#CC0000',
        'INC': '#1471C7',
        'IUML': '#006400',
        'KC(M)': '#FFD700',
        'NCP': '#00BFFF',
        'BJP': '#FF9900',
        'RSP': '#DC143C',
        'JD(S)': '#228B22',
        'KEC': '#8B008B',
        'OTH': '#95A5A6',
        'AWAITED': '#CCCCCC',
    },

    'alliances': {
        'LDF': {
            'parties': ['CPIM', 'CPI', 'RSP', 'JD(S)', 'KEC', 'NCP'],
            'color': '#FF0000',
            'description': 'CPIM, CPI, RSP, JD(S), KEC, NCP',
        },
        'UDF': {
            'parties': ['INC', 'IUML', 'KC(M)'],
            'color': '#1471C7',
            'description': 'INC, IUML, KC(M)',
        },
        'NDA': {
            'parties': ['BJP'],
            'color': '#FF9900',
            'description': 'Bharatiya Janata Party',
        },
        'OTH': {
            'parties': ['OTH'],
            'color': '#95A5A6',
            'description': 'Other Parties & Independents',
        },
    },

    'party_name_map': {
        'Communist Party of India (Marxist)': 'CPIM',
        'Communist Party of India': 'CPI',
        'Indian National Congress': 'INC',
        'Indian Union Muslim League': 'IUML',
        'Kerala Congress (M)': 'KC(M)',
        'Nationalist Congress Party': 'NCP',
        'Bharatiya Janata Party': 'BJP',
        'Revolutionary Socialist Party': 'RSP',
        'Janata Dal (Secular)': 'JD(S)',
        'Kerala Congress': 'KEC',
    },
}

# ── Puducherry ───────────────────────────────────────────────────────────────

PUDUCHERRY = {
    'name': 'Puducherry',
    'code': 'puducherry',
    'year': 2026,
    'election_event': 'ResultAcGenMay2026',
    'eci_state_code': 'U05',  # Union Territory
    'total_pages': 2,  # 30 seats / ~20 per page
    'total_seats': 30,
    'shapefile_st_name': 'PUDUCHERRY',
    'csv_file': 'election_results_puducherry.csv',
    'electors_file': 'electors_after_deletion_puducherry.csv',

    'parties': ['BJP', 'INC', 'DMK', 'AINRC', 'ADMK', 'NR', 'OTH', 'AWAITED'],

    'party_colors': {
        'BJP': '#FF9900',
        'INC': '#1471C7',
        'DMK': '#FF0000',
        'AINRC': '#006400',
        'ADMK': '#228B22',
        'NR': '#800080',
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
    },
}


# ── Bihar (TEST — real Nov 2025 results, used for pipeline speed testing) ────

BIHAR = {
    'name': 'Bihar',
    'code': 'bihar',
    'year': 2025,
    'election_event': 'ResultAcGenNov2025',
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
    'bihar': BIHAR,   # TEST — remove after verifying pipeline
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
