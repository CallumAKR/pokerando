#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PARTY_MENU = ROOT / "src/party_menu.c"
BATTLE_COMMANDS = ROOT / "src/battle_script_commands.c"
PLAYER_CONTROLLER = ROOT / "src/battle_controller_player.c"


class CapCandyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PARTY_MENU.read_text(encoding="utf-8")

    def test_learned_moves_resume_the_level_up_sequence(self):
        match = re.search(
            r"static void Task_LearnNextMoveOrClosePartyMenu\(u8 taskId\)"
            r"\n\{(?P<body>.*?)\n\}",
            self.source,
            re.DOTALL,
        )

        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("gPartyMenu.learnMoveState == 1", body)
        self.assertNotIn("gPartyMenu.data1 == 1", body)
        self.assertIn("Task_TryLearningNextMove(taskId);", body)

    def test_cap_candy_keeps_the_exact_cap_as_its_final_level(self):
        match = re.search(
            r"void ItemUseCB_CapCandy\(u8 taskId, TaskFunc task\)"
            r"\n\{(?P<body>.*?)\n\}",
            self.source,
            re.DOTALL,
        )

        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("targetLevel = levelCap;", body)
        self.assertIn("sFinalLevel = GetMonData(mon, MON_DATA_LEVEL);", body)
        self.assertIn(
            "gTasks[taskId].func = Task_DisplayLevelUpStatsPg1;",
            body,
        )

    def test_hard_cap_skips_zero_length_exp_bar_updates(self):
        commands = BATTLE_COMMANDS.read_text(encoding="utf-8")
        controller = PLAYER_CONTROLLER.read_text(encoding="utf-8")

        self.assertIn(
            "if (gBattleStruct->battlerExpReward == 0)",
            commands,
        )
        self.assertIn("gBattleScripting.getexpState = 5;", commands)
        self.assertIn("expPointsToGive <= 0", controller)


if __name__ == "__main__":
    unittest.main()
