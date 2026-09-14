import unittest

from edge_threat_response.domain import AlertState
from edge_threat_response.state_machine import AlertStateMachine
from edge_threat_response.temporal import KOfNBuffer


class TemporalTests(unittest.TestCase):
    def test_confirms_before_window_is_full_and_tolerates_dropout(self):
        buffer = KOfNBuffer(k=2, n=3)

        self.assertFalse(buffer.update(True).confirmed)
        self.assertTrue(buffer.update(True).confirmed)
        result = buffer.update(False)

        self.assertTrue(result.confirmed)
        self.assertEqual(2, result.true_count)

    def test_old_positive_expires(self):
        buffer = KOfNBuffer(k=2, n=3)
        for value in (True, True, False):
            buffer.update(value)

        self.assertFalse(buffer.update(False).confirmed)


class StateMachineTests(unittest.TestCase):
    def test_all_states_and_rearm(self):
        machine = AlertStateMachine(rearm_clear_frames=2)

        self.assertEqual(AlertState.CANDIDATE, machine.update(candidate=True, confirmed=False).after)
        entered = machine.update(candidate=True, confirmed=True)
        self.assertTrue(entered.entered_confirmed)
        self.assertEqual(AlertState.CONFIRMED, entered.after)
        exited = machine.update(candidate=False, confirmed=False)
        self.assertTrue(exited.exited_confirmed)
        self.assertEqual(AlertState.COOLDOWN, exited.after)
        self.assertEqual(
            AlertState.COOLDOWN,
            machine.update(candidate=False, confirmed=False).after,
        )
        self.assertEqual(
            AlertState.CLEAR,
            machine.update(candidate=False, confirmed=False).after,
        )

    def test_evidence_during_cooldown_resets_rearm_streak(self):
        machine = AlertStateMachine(rearm_clear_frames=2)
        machine.update(candidate=True, confirmed=True)
        machine.update(candidate=False, confirmed=False)
        evidence = machine.update(candidate=True, confirmed=True)

        self.assertEqual(AlertState.COOLDOWN, evidence.after)
        self.assertFalse(evidence.entered_confirmed)
        self.assertEqual(0, evidence.rearm_clear_streak)

    def test_confirmed_must_imply_candidate(self):
        with self.assertRaises(ValueError):
            AlertStateMachine(rearm_clear_frames=1).update(
                candidate=False, confirmed=True
            )


if __name__ == "__main__":
    unittest.main()
