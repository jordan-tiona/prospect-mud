"""Personal-name generator and checker for the seven peoples (bible 5.9).

Run from any directory:
  python ops/namegen/namegen.py                    # 10 names for every people
  python ops/namegen/namegen.py kell selk -n 20    # chosen peoples
  python ops/namegen/namegen.py --seed 7           # repeatable output
  python ops/namegen/namegen.py --check "Kedan Tolar"           # which peoples it fits
  python ops/namegen/namegen.py --check "Kedan Tolar" --people kell   # why it fails

Output is suggestions only: names are chosen by the owner, never placed in
the game by this tool. The rules live in rules.py; this module only applies
them. Standard library only, no Evennia imports, so the editor or chargen
can import it later.
"""

import argparse
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import rules

ROOT = Path(__file__).resolve().parents[2]
WORDS_FILE = Path(__file__).resolve().parent / 'data' / 'enable1.txt'
BLOCKLIST_FILE = Path(__file__).resolve().parent / 'data' / 'blocklist.txt'
SLOTS = ('given', 'family')
VOWELS = 'aeiou'

_RUN_RE = re.compile(f'[{VOWELS}]+|[^{VOWELS}]+')
_COMMENT_RE = re.compile(r'<!--(.*?)-->', re.S)
_H1_RE = re.compile(r'^# (.+)$', re.M)
MAX_TRIES = 2000


@dataclass
class Context:
    """Everything a check needs besides the rules: the word list and the excluded and translated names."""
    words: frozenset
    excluded: frozenset
    translated: dict = field(default_factory=dict)  # people -> [surname, ...]


def load_words(path=WORDS_FILE):
    with open(path, encoding='ascii') as f:
        return frozenset(line.strip() for line in f if line.strip())


def load_blocklist(path=BLOCKLIST_FILE):
    with open(path, encoding='utf-8') as f:
        return {line.strip().lower() for line in f if line.strip() and not line.startswith('#')}


def character_names(root=ROOT):
    """Name parts of every talk-capable NPC, from the H1 headings of content/npcs/*.md."""
    names = set()
    for path in sorted((Path(root) / 'content' / 'npcs').glob('*.md')):
        heading = _H1_RE.search(_COMMENT_RE.sub('', path.read_text(encoding='utf-8')))
        if heading:
            names.update(heading[1].split())
    return names


def load_translated(root=ROOT):
    """Approved translated-surname lists, by people. A list still marked Draft is not used."""
    lists = {}
    for people, relative in rules.TRANSLATED_SURNAMES.items():
        path = Path(root) / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        comment = _COMMENT_RE.search(text)
        if not comment or not re.search(r'^\s*approval:\s*Approved\s*$', comment[1], re.M):
            continue
        lines = (line.strip() for line in _COMMENT_RE.sub('', text).splitlines())
        lists[people] = [line for line in lines if line and not line.startswith('#')]
    return lists


def load_context(root=ROOT):
    excluded = {n.lower() for n in rules.EXCLUDED_NAMES} | {n.lower() for n in character_names(root)}
    excluded |= load_blocklist()
    return Context(load_words(), frozenset(excluded), load_translated(root))


def _pick(rng, inventory):
    """One item from a rules.py inventory: a list (uniform) or a dict of item -> weight."""
    if isinstance(inventory, dict):
        return rng.choices(list(inventory), weights=list(inventory.values()))[0]
    return rng.choice(inventory)


def _echoes(low):
    runs = _RUN_RE.findall(low)
    if any(runs[i][0] not in VOWELS and runs[i] == runs[i + 2] and len(runs[i + 1]) == 1
           for i in range(len(runs) - 2)):
        return True
    return bool(re.search(r'(.{2,})\1', low))


def twins(a, b):
    """True if two name parts are the same or differ by a single letter."""
    a, b = a.lower(), b.lower()
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1


def _shared_issues(low, ctx):
    issues = []
    if not re.fullmatch('[a-z]+', low):
        return ['letters a-z only']
    if len(low) < rules.MIN_LETTERS:
        issues.append(f'shorter than {rules.MIN_LETTERS} letters (tuning)')
    issues += [f'contains "{s}"' for s in rules.BANNED_SUBSTRINGS if s in low]
    if re.search(f'y(?![{VOWELS}])', low):
        issues.append('"y" used as a vowel')
    if re.search(r'(.)\1\1', low):
        issues.append('tripled letter')
    if rules.REJECT_ECHOES and _echoes(low):
        issues.append('echoed syllable (tuning)')
    if low in ctx.excluded:
        issues.append('excluded name (a people, place, existing character or blocklist entry)')
    if low in ctx.words:
        issues.append('English dictionary word')
    return issues


def rule_issues(part, people, slot):
    """Ways `part` breaks one people's row of 5.9, as a list of short reasons (empty if it fits)."""
    r = rules.PEOPLES[people]
    low = part.lower()
    if not re.fullmatch('[a-z]+', low):
        return ['letters a-z only']
    issues = []
    runs = _RUN_RE.findall(low)
    onset = runs[0] if runs[0][0] not in VOWELS else ''
    body = runs[1:] if onset else runs
    if not body:
        return ['no vowel']
    coda = body[-1] if body[-1][0] not in VOWELS else ''
    core = body[:-1] if coda else body
    nuclei, medials = core[0::2], core[1::2]

    syllables = sum(len(n) for n in nuclei)
    lo, hi = r['syllables'][slot]
    if not lo <= syllables <= hi:
        want = str(lo) if lo == hi else f'{lo}-{hi}'
        issues.append(f'{syllables} syllables ({slot} wants {want})')

    if onset not in r['onsets']:
        issues.append(f'onset "{onset or "(vowel)"}" not allowed')
    elif not onset and nuclei[0][0] not in r['bare_vowels']:
        issues.append(f'may not start with "{nuclei[0][0]}"')

    for m in medials:
        if m not in r['medials']:
            issues.append(f'middle "{m}" not allowed')
    for n in nuclei:
        if len(n) > 1 and n not in r['hiatus']:
            issues.append(f'vowels "{n}" together')

    if r['rimes']:
        rime = next((e for e in r['rimes'] if low.endswith(e) and len(nuclei[-1]) == 1
                     and coda == e[1:] and nuclei[-1] == e[0]), None)
        if rime is None:
            issues.append('ending not one of ' + ', '.join(f'-{e}' for e in r['rimes']))
        checked = ''.join(nuclei)[:-1]
    else:
        if coda not in r['codas']:
            issues.append(f'ending "-{coda}" not allowed' if coda else 'open-vowel ending not allowed')
        elif not coda and nuclei[-1][-1] not in r['open_ends']:
            issues.append(f'may not end on "{nuclei[-1][-1]}"')
        checked = ''.join(nuclei)
    for v in sorted(set(checked) - set(r['vowels'])):
        issues.append(f'vowel "{v}" not allowed')

    for f in r['forbid']:
        if f in low:
            issues.append(f'contains "{f}"')
    if r['no_doubles'] and re.search(f'([^{VOWELS}])\\1', low):
        issues.append('doubled consonant')
    if people == 'revari':
        if syllables == 3 and low.endswith('ari'):
            issues.append('three-syllable -ari form')
        clusters = [c for c in [onset, coda] + medials if len(c) > 1 and c not in rules.DIGRAPHS]
        if len(clusters) > rules.REVARI_MAX_CLUSTERS:
            issues.append(f'{len(clusters)} consonant clusters (tuning: at most {rules.REVARI_MAX_CLUSTERS})')
    return issues


def part_issues(part, people, slot, ctx):
    """Every reason `part` can't be used as this people's given or family name."""
    low = part.lower()
    if slot == 'family' and part in ctx.translated.get(people, ()):
        return []  # authored list: exempt from the shape and dictionary rules
    return _shared_issues(low, ctx) + rule_issues(part, people, slot)


def fits(given, family, people):
    """True if the name fits this people's row, ignoring the shared exclusions."""
    return not rule_issues(given, people, 'given') and not rule_issues(family, people, 'family')


def name_issues(given, family, people, ctx):
    """Every reason "given family" can't be used as a name of this people, prefixed by the part."""
    issues = [f'{given}: {i}' for i in part_issues(given, people, 'given', ctx)]
    issues += [f'{family}: {i}' for i in part_issues(family, people, 'family', ctx)]
    if rules.REJECT_TWINS and twins(given, family):
        issues.append('given and family names nearly identical (tuning)')
    if people == 'revari' and not issues:
        owners = [p for p in rules.PEOPLES if p != 'revari' and fits(given, family, p)]
        if len(owners) == 1:
            issues.append(f'reads as a {rules.PEOPLES[owners[0]]["name"]} name only')
    return issues


@dataclass(frozen=True)
class Name:
    given: str
    family: str
    people: str
    sources: tuple  # (given's people, family's people); differ from `people` when borrowed
    translated: bool = False

    def __str__(self):
        return f'{self.given} {self.family}'

    def note(self):
        notes = [f'{slot} from {rules.PEOPLES[src]["name"]}'
                 for slot, src in zip(SLOTS, self.sources) if src != self.people]
        if self.translated:
            notes.append('translated surname')
        return ', '.join(notes)


def _candidate(rng, people, slot):
    r = rules.PEOPLES[people]
    lo, hi = r['syllables'][slot]
    syllables = rng.randint(lo, hi)
    onset = _pick(rng, r['onsets'])
    rime = rng.choice(r['rimes']) if r['rimes'] else None
    count = syllables - 1 if rime else syllables
    nuclei = [rng.choice(r['bare_vowels'] if i == 0 and not onset else r['vowels']) for i in range(count)]
    coda = ''
    if not rime:
        coda = _pick(rng, r['codas'])
        if not coda:
            nuclei[-1] = rng.choice(r['open_ends'])
    joins = []
    for i in range(count - 1):
        if r['hiatus'] and rng.random() < rules.LIRRA_HIATUS_CHANCE:
            pair = rng.choice(r['hiatus'])
            nuclei[i], nuclei[i + 1] = pair[0], pair[1]
            joins.append('')
        else:
            joins.append(_pick(rng, r['medials']))
    text = onset + ''.join(n + j for n, j in zip(nuclei, joins + ['']))
    if rime:
        text += (_pick(rng, r['medials']) if count else '') + rime
    else:
        text += coda
    return text.capitalize()


def make_part(rng, people, slot, ctx):
    for _ in range(MAX_TRIES):
        part = _candidate(rng, people, slot)
        if not part_issues(part, people, slot, ctx):
            return part
    raise RuntimeError(f'no valid {people} {slot} name in {MAX_TRIES} tries; check rules.py')


def make_name(rng, people, ctx, borrow=rules.DEFAULT_BORROW, translated=rules.DEFAULT_TRANSLATED):
    for _ in range(MAX_TRIES):
        sources = [people, people]
        if rng.random() < borrow:
            sources[rng.randrange(2)] = rng.choice([p for p in rules.PEOPLES if p != people])
        given = make_part(rng, sources[0], 'given', ctx)
        surnames = ctx.translated.get(sources[1])
        is_translated = bool(surnames) and rng.random() < translated
        family = rng.choice(surnames) if is_translated else make_part(rng, sources[1], 'family', ctx)
        if rules.REJECT_TWINS and twins(given, family):
            continue
        if sources == [people, people] and name_issues(given, family, people, ctx):
            continue
        return Name(given, family, people, tuple(sources), is_translated)
    raise RuntimeError(f'no valid {people} name in {MAX_TRIES} tries; check rules.py')


def generate(people, count, ctx, rng=None, **kwargs):
    """`count` distinct names for one people."""
    rng = rng or random.Random()
    names, seen = [], set()
    for _ in range(count * 50):
        if len(names) == count:
            break
        name = make_name(rng, people, ctx, **kwargs)
        if str(name) not in seen:
            seen.add(str(name))
            names.append(name)
    return names


def _people_arg(value):
    key = value.lower()
    if key not in rules.PEOPLES:
        raise argparse.ArgumentTypeError(f'unknown people "{value}" (one of: {", ".join(rules.PEOPLES)})')
    return key


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate or check personal names (bible 5.9).')
    parser.add_argument('peoples', nargs='*', type=_people_arg, help='peoples to generate for (default: all)')
    parser.add_argument('-n', '--count', type=int, default=10, help='names per people (default 10)')
    parser.add_argument('--seed', type=int, help='random seed, for repeatable output')
    parser.add_argument('--borrow', type=float, default=rules.DEFAULT_BORROW,
                        help=f'chance a name borrows one part from another people (default {rules.DEFAULT_BORROW})')
    parser.add_argument('--translated', type=float, default=rules.DEFAULT_TRANSLATED,
                        help=f'chance of a translated surname where allowed (default {rules.DEFAULT_TRANSLATED})')
    parser.add_argument('--check', metavar='"GIVEN FAMILY"', help='check a name instead of generating')
    parser.add_argument('--people', type=_people_arg, help='with --check: explain against this people')
    args = parser.parse_args(argv)
    ctx = load_context()

    if args.check:
        parts = args.check.split()
        if len(parts) != 2:
            parser.error('--check takes a given and a family name, e.g. --check "Kedan Tolar"')
        given, family = parts
        if args.people:
            issues = name_issues(given, family, args.people, ctx)
            print(f'{args.check}: ' + ('fits ' + rules.PEOPLES[args.people]['name'] if not issues else 'does not fit'))
            for issue in issues:
                print(f'  - {issue}')
            return 1 if issues else 0
        fitting = [rules.PEOPLES[p]['name'] for p in rules.PEOPLES if not name_issues(given, family, p, ctx)]
        print(f'{args.check}: ' + (f'fits {", ".join(fitting)}' if fitting else 'fits no people'))
        return 0 if fitting else 1

    rng = random.Random(args.seed)
    for i, people in enumerate(args.peoples or list(rules.PEOPLES)):
        if i:
            print()
        print(rules.PEOPLES[people]['name'])
        for name in generate(people, args.count, ctx, rng, borrow=args.borrow, translated=args.translated):
            note = name.note()
            print(f'  {str(name):<24}{f"({note})" if note else ""}'.rstrip())
    return 0


if __name__ == '__main__':
    sys.exit(main())
