"""Tests for the name generator and checker.

Run from the repo root:  python -m unittest discover -s ops/namegen
"""

import contextlib
import io
import random
import tempfile
import unittest
from pathlib import Path

import namegen
import rules

CTX = namegen.load_context()

# Bible 5.9's illustrative output, as of 2026-10-17.
EXAMPLES = {
    'kell': ['Kedan Tolar', 'Dorem Gabel', 'Tam Bodon'],
    'drask': ['Krast Trak', 'Stobak Drosk', 'Krotas Brust'],
    'lirra': ['Alira Wenno', 'Orro Elia', 'Lenni Yaro'],
    'revari': ['Corin Tavel', 'Tamsin Ellis', 'Maren Oskel'],
    'astrel': ['Oslen Stel', 'Islan Skel', 'Spinas Asil'],
    'voldren': ['Vordar Bargor', 'Goldur Dandor', 'Vundar Stonebreaker'],
    'selk': ['Sulim Thesk', 'Selm Mesk', 'Mithen Thul'],
}

# Examples that break 5.9's own written rules, reported to the owner
# 2026-10-17. When 5.9 changes, update EXAMPLES and this list together.
KNOWN_MISMATCHES = {
    'Tam Bodon': 'English dictionary word',     # "tam" is in ENABLE
    'Orro Elia': '3 syllables',                 # e-li-a; Lirra family names are 2
    'Oslen Stel': 'vowel "o" not allowed',      # Astrel vowels are a, e, i
}


class ExampleTests(unittest.TestCase):
    def test_bible_examples_fit_their_people(self):
        for people, names in EXAMPLES.items():
            for name in names:
                if name in KNOWN_MISMATCHES:
                    continue
                with self.subTest(name=name):
                    self.assertEqual(namegen.name_issues(*name.split(), people, CTX), [])

    def test_known_mismatches_still_fail_for_the_reported_reason(self):
        for people, names in EXAMPLES.items():
            for name in names:
                if name in KNOWN_MISMATCHES:
                    with self.subTest(name=name):
                        issues = namegen.name_issues(*name.split(), people, CTX)
                        self.assertTrue(any(KNOWN_MISMATCHES[name] in i for i in issues), issues)


class GeneratorTests(unittest.TestCase):
    def test_every_generated_name_passes_its_sources_rules(self):
        rng = random.Random(1)
        for people in rules.PEOPLES:
            for name in namegen.generate(people, 150, CTX, rng):
                with self.subTest(people=people, name=str(name)):
                    if name.sources == (people, people):
                        self.assertEqual(namegen.name_issues(name.given, name.family, people, CTX), [])
                    else:
                        self.assertEqual(namegen.part_issues(name.given, name.sources[0], 'given', CTX), [])
                        self.assertEqual(namegen.part_issues(name.family, name.sources[1], 'family', CTX), [])

    def test_names_are_distinct_and_counted(self):
        names = namegen.generate('kell', 30, CTX, random.Random(2))
        self.assertEqual(len(names), 30)
        self.assertEqual(len({str(n) for n in names}), 30)

    def test_seed_repeats_output(self):
        first = namegen.generate('selk', 10, CTX, random.Random(5))
        second = namegen.generate('selk', 10, CTX, random.Random(5))
        self.assertEqual([str(n) for n in first], [str(n) for n in second])

    def test_no_borrowing_keeps_every_part_home(self):
        for name in namegen.generate('drask', 50, CTX, random.Random(3), borrow=0):
            self.assertEqual(name.sources, ('drask', 'drask'))

    def test_translated_surnames_only_for_voldren_and_only_from_the_list(self):
        surnames = set(CTX.translated['voldren'])
        names = namegen.generate('voldren', 60, CTX, random.Random(4), borrow=0, translated=1)
        self.assertTrue(all(n.family in surnames and n.translated for n in names))
        for name in namegen.generate('astrel', 60, CTX, random.Random(4), borrow=0, translated=1):
            self.assertFalse(name.translated)


class CheckTests(unittest.TestCase):
    def issues(self, part, people='kell', slot='given'):
        return namegen.part_issues(part, people, slot, CTX)

    def test_shared_exclusions(self):
        self.assertIn('English dictionary word', ' '.join(self.issues('Bat')))
        for excluded in ('Kell', 'Kethari', 'Haven', 'Daven', 'Talin', 'Gondor'):
            self.assertIn('excluded name', ' '.join(self.issues(excluded)), excluded)

    def test_readability(self):
        self.assertIn('contains "ae"', ' '.join(self.issues('Daen', 'revari')))
        self.assertIn('"y" used as a vowel', ' '.join(self.issues('Lyra', 'lirra')))
        self.assertIn('letters a-z only', ' '.join(self.issues("Ke'dan")))
        self.assertIn('shorter than', ' '.join(self.issues('Ek')))

    def test_row_rules(self):
        self.assertIn('onset "s"', ' '.join(self.issues('Selan')))                            # Kell stops only
        self.assertIn('doubled consonant', ' '.join(self.issues('Bannel')))                  # Kell
        self.assertIn('open-vowel ending', ' '.join(self.issues('Kraka', 'drask')))
        self.assertIn('2 syllables', ' '.join(self.issues('Krotak', 'drask', 'family')))
        self.assertIn('may not end on "e"', ' '.join(self.issues('Alire', 'lirra')))
        self.assertIn('middle "st"', ' '.join(self.issues('Alista', 'lirra')))
        self.assertIn('1 syllables', ' '.join(self.issues('Vord', 'voldren')))
        self.assertIn('middle "d"', ' '.join(self.issues('Vodar', 'voldren')))
        self.assertIn('contains "r"', ' '.join(self.issues('Serim', 'selk')))

    def test_revari_rejects_a_name_only_one_other_people_owns(self):
        self.assertTrue(namegen.fits('Telan', 'Bodel', 'kell'))
        self.assertIn('reads as a Kell name only', ' '.join(namegen.name_issues('Telan', 'Bodel', 'revari', CTX)))

    def test_revari_cluster_limit(self):
        self.assertIn('consonant clusters', ' '.join(self.issues('Skastrin', 'revari')))

    def test_translated_surname_is_family_only(self):
        self.assertEqual(self.issues('Stonebreaker', 'voldren', 'family'), [])
        self.assertTrue(self.issues('Stonebreaker', 'voldren', 'given'))
        self.assertTrue(self.issues('Stonebreaker', 'kell', 'family'))

    def test_near_identical_parts(self):
        self.assertIn('nearly identical', ' '.join(namegen.name_issues('Doldar', 'Daldar', 'voldren', CTX)))


class LoaderTests(unittest.TestCase):
    def test_draft_surname_list_is_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / rules.TRANSLATED_SURNAMES['voldren']
            path.parent.mkdir(parents=True)
            path.write_text('<!--\napproval: Draft\n-->\n\n# List\n\nDeepcutter\n', encoding='utf-8')
            self.assertEqual(namegen.load_translated(tmp), {})
            path.write_text('<!--\napproval: Approved\n-->\n\n# List\n\nDeepcutter\n', encoding='utf-8')
            self.assertEqual(namegen.load_translated(tmp), {'voldren': ['Deepcutter']})

    def test_character_names_come_from_persona_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            npcs = Path(tmp) / 'content' / 'npcs'
            npcs.mkdir(parents=True)
            (npcs / 'x.md').write_text('# Bodan Kerel\n\n<!--\nnpc_id: x\n-->\n', encoding='utf-8')
            self.assertEqual(namegen.character_names(tmp), {'Bodan', 'Kerel'})


class CliTests(unittest.TestCase):
    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = namegen.main(list(argv))
        return code, out.getvalue()

    def test_generate(self):
        code, out = self.run_main('kell', 'selk', '-n', '3', '--seed', '1')
        self.assertEqual(code, 0)
        self.assertIn('Kell', out)
        self.assertIn('Selk', out)

    def test_check(self):
        self.assertEqual(self.run_main('--check', 'Kedan Tolar', '--people', 'kell')[0], 0)
        code, out = self.run_main('--check', 'Kedan Tolar', '--people', 'selk')
        self.assertEqual(code, 1)
        self.assertIn('onset', out)
        self.assertIn('fits Kell', self.run_main('--check', 'Kedan Tolar')[1])


if __name__ == '__main__':
    unittest.main()
