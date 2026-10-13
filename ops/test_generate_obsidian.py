"""Checks the source-data boundary and repeatable regeneration using copied inputs."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from generate_obsidian import MAP, MARKER, ROOT, generate


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'content', self.root / 'content')
        world = self.root / 'prospect/world'
        world.mkdir(parents=True)
        for filename in ('build_rooms.py', 'build_npcs.py', 'build_ambient.py'):
            shutil.copy2(ROOT / 'prospect/world' / filename, world / filename)
        (self.root / 'maps').mkdir()
        shutil.copy2(ROOT / 'maps/README.md', self.root / 'maps/README.md')
        shutil.copy2(ROOT / MAP, self.root / MAP)

    def test_sources_unchanged_and_second_run_identical(self):
        before = (snapshot(self.root / 'content'), snapshot(self.root / 'prospect'))
        generate(self.root)
        first = snapshot(self.root / 'maps')
        generate(self.root)
        self.assertEqual(first, snapshot(self.root / 'maps'))
        self.assertEqual(before, (snapshot(self.root / 'content'), snapshot(self.root / 'prospect')))

    def test_builder_entities_only_and_bidirectional_navigation(self):
        generate(self.root)
        square = (self.root / 'maps/rooms/old_quarter_square.md').read_text(encoding='utf-8')
        cafe = (self.root / 'maps/rooms/corner_cafe.md').read_text(encoding='utf-8')
        self.assertIn('**North:** [[maps/rooms/corner_cafe|', square)
        self.assertIn('**South:** [[maps/rooms/old_quarter_square|', cafe)
        self.assertIn('square_noticeboard', square)
        self.assertNotIn('square_benches', square)
        self.assertNotIn('square_planting_beds', square)
        draft = self.root / 'content/ambient/objects/square_noticeboard.md'
        draft.write_text(draft.read_text(encoding='utf-8').replace('approval: Approved', 'approval: Draft'), encoding='utf-8')
        generate(self.root)
        self.assertNotIn('square_noticeboard', (self.root / 'maps/rooms/old_quarter_square.md').read_text(encoding='utf-8'))

    def test_preserves_custom_layout(self):
        path = self.root / MAP
        canvas = json.loads(path.read_text(encoding='utf-8-sig'))
        room = next(n for n in canvas['nodes'] if n['id'] == 'corner_cafe')
        room.update(x=1234, y=-987, width=500, height=300, color='3')
        path.write_text(json.dumps(canvas), encoding='utf-8')
        generate(self.root)
        updated = next(n for n in json.loads(path.read_text(encoding='utf-8'))['nodes'] if n['id'] == 'corner_cafe')
        for key in ('x', 'y', 'width', 'height', 'color'):
            self.assertEqual(room[key], updated[key])

    def test_missing_source_fails_before_changing_outputs(self):
        before = snapshot(self.root / 'maps')
        (self.root / 'content/npcs/mara_voss.md').unlink()
        with self.assertRaises(FileNotFoundError):
            generate(self.root)
        self.assertEqual(before, snapshot(self.root / 'maps'))

    def test_preserves_user_notes_and_cleans_only_owned_stale_notes(self):
        notes = self.root / 'maps/rooms'
        notes.mkdir()
        hand = notes / 'personal.md'
        hand.write_text('Personal map notes.', encoding='utf-8')
        stale = notes / 'obsolete.md'
        stale.write_text(MARKER + '\n', encoding='utf-8')
        generate(self.root)
        self.assertTrue(hand.exists())
        self.assertFalse(stale.exists())
        collision = notes / 'corner_cafe.md'
        collision.write_text('Personal map notes.', encoding='utf-8')
        before = snapshot(self.root / 'maps')
        with self.assertRaisesRegex(ValueError, 'hand-authored'):
            generate(self.root)
        self.assertEqual(before, snapshot(self.root / 'maps'))


if __name__ == '__main__':
    unittest.main()
