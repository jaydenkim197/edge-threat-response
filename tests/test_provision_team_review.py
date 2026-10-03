import json
import tempfile
import unittest
from pathlib import Path

from tools.provision_team_review import provision
from edge_threat_response.dataset.team_review import TeamDatabase


class ProvisionTeamReviewTests(unittest.TestCase):
    def test_codes_are_saved_once_and_each_account_can_log_in(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            database = root / "team.sqlite3"
            output = root / "secrets" / "codes.txt"
            config.write_text(json.dumps({"database": str(database), "public_url": "https://review.example.test/"}))
            self.assertEqual(2, provision(config, output, ["검수자 가", "검수자 나"]))
            entries = [line.split("\t") for line in output.read_text(encoding="utf-8").splitlines() if "\t" in line]
            self.assertEqual(["검수자 가", "검수자 나"], [entry[0] for entry in entries])
            team = TeamDatabase(database)
            for name, code in entries:
                self.assertEqual(name, team.login(code)["name"])
            with self.assertRaises(ValueError):
                provision(config, root / "other-codes.txt", ["검수자 가"])
            self.assertFalse((root / "other-codes.txt").exists())
            with self.assertRaises(FileExistsError):
                provision(config, output, ["검수자 다"])
            with team.connect() as connection:
                self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
