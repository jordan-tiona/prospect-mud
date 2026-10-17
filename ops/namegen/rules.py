"""Per-people personal-name rules, transcribed from bible 5.9 (docs/bible/s05-peoples.md).

Bible 5.9 is the source; this file is the generator's reading of it. When 5.9
changes, change the matching entry here. Where 5.9 is silent, the choice is a
Tools-lane tuning value and is marked `# tuning:`; those are the first things
to adjust when the owner judges the output.

Each people has:
  syllables   {'given': (min, max), 'family': (min, max)}
  onsets      consonant onsets; '' means a bare-vowel start is allowed
  bare_vowels vowels a name may start with when the onset is ''
  vowels      vowels allowed anywhere other than inside an ending rime
  medials     consonant runs allowed between two vowels
  hiatus      vowel pairs allowed with no consonant between (each vowel is a syllable)
  codas       final consonant runs; '' means an open-vowel ending is allowed
  open_ends   vowels a name may end on, when '' is a coda
  rimes       endings that bring their own vowel ('-an', '-ar'); replaces codas
  forbid      letters or digraphs that may not appear anywhere
  no_doubles  reject any doubled consonant
  heavy       (optional) every part must contain at least one of these middles

Any inventory may be a list (picked uniformly) or a dict of item -> weight
(picked in proportion). Weights only steer the generator; the checker treats
every listed item as allowed.
"""

STOPS = ['k', 't', 'd', 'b', 'g']

PEOPLES = {
    'kell': {
        'name': 'Kell',
        'syllables': {'given': (2, 3), 'family': (1, 2)},
        'onsets': STOPS,
        'bare_vowels': [],
        'vowels': ['a', 'e', 'o'],
        # tuning: 5.9 gives no middle consonants; single, non-sibilant (Kedan, Dorem, Gabel)
        'medials': ['b', 'd', 'g', 'k', 't', 'l', 'm', 'n', 'r', 'v'],
        'hiatus': [],
        'codas': ['l', 'n', 'm', 'r'],
        'open_ends': [],
        'rimes': [],
        'forbid': ['s', 'z', 'x', 'c', 'j'],  # "avoid sibilants"
        'no_doubles': True,  # "clusters, including doubled consonants"
    },
    'drask': {
        'name': 'Drask',
        'syllables': {'given': (1, 2), 'family': (1, 2)},
        'onsets': ['dr', 'tr', 'kr', 'br', 'sk', 'st'],
        'bare_vowels': [],
        'vowels': ['a', 'o', 'u'],
        # tuning: hard middles, plus the row's own clusters (Stobak, Krotas)
        'medials': ['b', 'd', 'g', 'k', 't', 'v', 'm', 'n', 'r', 's', 'st', 'sk'],
        'hiatus': [],
        'codas': ['k', 't', 's', 'sk', 'st'],
        'open_ends': [],
        'rimes': [],
        'forbid': [],
        'no_doubles': False,
    },
    'lirra': {
        'name': 'Lirra',
        'syllables': {'given': (2, 3), 'family': (2, 2)},
        'onsets': ['', 'l', 'r', 'w', 'y'],
        'bare_vowels': ['a', 'e', 'i', 'o'],
        'vowels': ['a', 'e', 'i', 'o'],
        # tuning: soft single middles plus the row's doubled ll, rr, nn
        # tuning: doubled middles about one middle in four, counting the bare
        # vowel pairs below (owner, 2026-10-17)
        'medials': {'l': 3, 'r': 3, 'n': 3, 'm': 3, 'v': 3, 'w': 2, 'll': 3, 'rr': 3, 'nn': 3},
        # tuning: "open, often two in a row"; only pairs an English reader splits
        # into two syllables (Elia). ea/ou/oa read as one sound; ae/ei are banned.
        'hiatus': ['ia', 'io', 'eo'],
        'codas': [''],
        'open_ends': ['a', 'i', 'o'],
        'rimes': [],
        'forbid': [],
        'no_doubles': False,
    },
    'revari': {
        'name': 'Revari',
        'syllables': {'given': (2, 3), 'family': (1, 2)},
        'onsets': None,  # "any, drawn from the other six tables": filled in below
        'bare_vowels': ['a', 'e', 'i', 'o', 'u'],
        'vowels': ['a', 'e', 'i', 'o', 'u'],
        'medials': None,  # the other six tables' middles, plus EXTRA_REVARI_MEDIALS
        'hiatus': [],
        'codas': [],
        'open_ends': [],
        'rimes': ['an', 'en', 'in', 'is', 'el'],
        'forbid': [],
        'no_doubles': False,
    },
    'astrel': {
        'name': 'Astrel',
        'syllables': {'given': (1, 2), 'family': (1, 2)},
        # tuning: about half start on a bare vowel, spread evenly over a/e/i
        # (owner, 2026-10-17). Not o: it makes them read as Drask.
        'onsets': {'st': 1, 'sk': 1, 'sp': 1, 'sl': 1, '': 4},
        'bare_vowels': ['a', 'e', 'i'],
        'vowels': ['a', 'e', 'i'],
        # tuning: the row's s-clusters in the middle too (Oslen, Islan)
        'medials': {'l': 3, 'n': 3, 's': 2, 't': 2, 'k': 2, 'p': 2, 'v': 2, 'm': 2,
                    'st': 1, 'sk': 1, 'sp': 1, 'sl': 1},
        'hiatus': [],
        'codas': ['l', 'n', 's'],
        'open_ends': [],
        'rimes': [],
        'forbid': [],
        'no_doubles': True,
    },
    'voldren': {
        'name': 'Voldren',
        'syllables': {'given': (2, 3), 'family': (2, 2)},
        'onsets': ['v', 'b', 'd', 'g'],
        'bare_vowels': [],
        'vowels': ['a', 'o', 'u'],
        # "a plain -l-, -r-, -n-, -d- may join the other syllables, but every
        # name part keeps at least one heavy cluster"; tuning: weights
        'medials': {'ld': 3, 'rd': 3, 'nd': 3, 'rg': 3, 'l': 1, 'r': 1, 'n': 1, 'd': 1},
        'heavy': ['ld', 'rd', 'nd', 'rg'],
        'hiatus': [],
        'codas': [],
        'open_ends': [],
        'rimes': ['ar', 'or', 'ur', 'en'],
        'forbid': [],
        'no_doubles': False,
    },
    'selk': {
        'name': 'Selk',
        'syllables': {'given': (1, 2), 'family': (1, 2)},
        'onsets': ['s', 'sh', 'th', 'm'],
        'bare_vowels': [],
        'vowels': ['e', 'i', 'u'],
        # tuning: soft middles (Sulim, Mithen); no r ("r-heavy")
        'medials': ['k', 'l', 'm', 'n', 's', 'sh', 'th'],
        'hiatus': [],
        # tuning: -lk/-lm as well as the listed singles, per the people's own
        # name and the example Selm
        'codas': {'k': 3, 'l': 3, 'm': 3, 'n': 3, 'sk': 2, 'lk': 1, 'lm': 1},
        'open_ends': [],
        'rimes': [],
        'forbid': ['r'],
        'no_doubles': False,
    },
}

# tuning: Revari is "built from borrowing", so it takes every other table's
# onsets and middles. 'c' covers the example Corin; the extra middles cover
# Tamsin and similar English-familiar shapes. Endings must be "familiar to an
# English reader", so single consonants are weighted well above clusters, and
# a Revari part may hold at most one cluster (REVARI_MAX_CLUSTERS).
EXTRA_REVARI_ONSETS = ['c']
EXTRA_REVARI_MEDIALS = ['ms', 'ns', 'nt', 'ls', 'lv', 'rv']
REVARI_MAX_CLUSTERS = 1
DIGRAPHS = ['th', 'sh']  # one sound each, so not clusters


def _revari_weights(items):
    return {i: (4 if len(i) == 1 or i in DIGRAPHS else 2 if i == '' else 1) for i in sorted(items)}


_others = [p for key, p in PEOPLES.items() if key != 'revari']
PEOPLES['revari']['onsets'] = _revari_weights({o for p in _others for o in p['onsets']} | set(EXTRA_REVARI_ONSETS))
PEOPLES['revari']['medials'] = _revari_weights({m for p in _others for m in p['medials']} | set(EXTRA_REVARI_MEDIALS))

# Shared readability rule: these never appear.
BANNED_SUBSTRINGS = ['ae', 'ei', "'"]

# 5.9's shared Length rule: "within a row's range, lean toward the longer
# end". tuning: weights for one, two and three syllables within each range.
SYLLABLE_WEIGHTS = {1: 1, 2: 3, 3: 2}

# tuning: not in 5.9. Reject echoes (Bobar, Gogor, Thithilm: the same
# consonants either side of one vowel; Gorgor: a repeated chunk); "twins",
# parts within one letter of each other (one letter changed, added or
# removed): a given and family name that are twins (Doldar Daldar), a part
# that twins one already emitted in the same batch (owner, 2026-10-17), and
# a part that adds or drops a letter of an excluded name, or changes only its
# first letter (Dras, Rirra; but not Drosk or Selm, owner 2026-10-17).
REJECT_ECHOES = True
REJECT_TWINS = True
MIN_LETTERS = 3  # tuning: Il, Ek read as fragments, not names

# Shared exclusion rule. Existing characters' names are also read from the
# H1 headings of content/npcs/*.md, so new NPCs are excluded automatically.
EXCLUDED_NAMES = [
    # the seven peoples
    'Kell', 'Drask', 'Lirra', 'Revari', 'Astrel', 'Voldren', 'Selk',
    # superseded names
    'Kethari', 'Sylari', 'Aevyrin', 'Naevari', 'Otheryn', 'Neshyr',
    # place and field names
    'Prospect', 'Haven', 'Elsewhere', 'Venn', 'Saye',
    # existing characters named in 5.9
    'Daven', 'Varek', 'Tarin', 'Os', 'Veska', 'Renn', 'Iri', 'Vael', 'Mara', 'Voss',
    'Given', 'Marr', 'Sera', 'Talin',
]

# The only people whose row allows translated descriptive surnames, and the
# authored list they come from (LR-TOOLS-0004).
TRANSLATED_SURNAMES = {'voldren': 'content/names/voldren-translated-surnames.md'}

# tuning: defaults for the generator.
DEFAULT_BORROW = 0.15        # chance a name takes one part from another people
DEFAULT_TRANSLATED = 0.25    # chance a Voldren family name is translated (Lore's suggestion)
LIRRA_HIATUS_CHANCE = 0.3    # chance a Lirra middle is a bare vowel pair
