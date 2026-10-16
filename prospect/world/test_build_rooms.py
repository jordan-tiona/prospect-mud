"""
Tests for world/build_rooms.py: the room graph, including the three
rooms added for the initial playtest (Medical Bay, Old Quarter
Street, Daven's Office) and the project owner's 2026-10-14 exit
choices (docs/prospect-initial-playtest-design-spec.md).

Run with:
    evennia test world
"""

from django.test import TestCase

from world.build_rooms import build


def _exit_keys(room, destination):
    return [exi.key for exi in room.exits if exi.destination == destination]


class BuildRoomsTests(TestCase):
    def setUp(self):
        self.rooms = build()

    def test_all_nine_rooms_exist(self):
        for tag in (
            "lift_concourse",
            "old_quarter_square",
            "corner_cafe",
            "maintenance_workshop",
            "residential_courtyard",
            "civic_office",
            "medical_bay",
            "old_quarter_street",
            "daven_office",
        ):
            self.assertIn(tag, self.rooms)

    def test_rerun_does_not_duplicate_rooms_or_exits(self):
        build()
        self.assertEqual(len(self.rooms["old_quarter_square"].exits), 6)

    def test_square_to_lift_concourse_is_northeast(self):
        square = self.rooms["old_quarter_square"]
        lift = self.rooms["lift_concourse"]
        self.assertEqual(_exit_keys(square, lift), ["northeast"])
        self.assertEqual(_exit_keys(lift, square), ["southwest"])

    def test_square_to_street_is_southwest(self):
        square = self.rooms["old_quarter_square"]
        street = self.rooms["old_quarter_street"]
        self.assertEqual(_exit_keys(square, street), ["southwest"])
        self.assertEqual(_exit_keys(street, square), ["northeast"])

    def test_lift_concourse_to_medical_bay_is_up(self):
        lift = self.rooms["lift_concourse"]
        medical_bay = self.rooms["medical_bay"]
        self.assertEqual(_exit_keys(lift, medical_bay), ["up"])
        self.assertEqual(_exit_keys(medical_bay, lift), ["down"])

    def test_street_to_davens_office_is_north(self):
        street = self.rooms["old_quarter_street"]
        office = self.rooms["daven_office"]
        self.assertEqual(_exit_keys(street, office), ["north"])
        self.assertEqual(_exit_keys(office, street), ["south"])

    def test_original_four_cardinal_spokes_unchanged(self):
        square = self.rooms["old_quarter_square"]
        self.assertEqual(_exit_keys(square, self.rooms["corner_cafe"]), ["north"])
        self.assertEqual(_exit_keys(square, self.rooms["residential_courtyard"]), ["south"])
        self.assertEqual(_exit_keys(square, self.rooms["maintenance_workshop"]), ["east"])
        self.assertEqual(_exit_keys(square, self.rooms["civic_office"]), ["west"])

    def test_full_route_from_medical_bay_to_davens_office(self):
        from world.actions import _find_exit_path

        path = _find_exit_path(self.rooms["medical_bay"], self.rooms["daven_office"])
        self.assertEqual(path, ["down", "southwest", "southwest", "north"])
