import unittest
from hashlib import md5

from plugins.endfield.account_detail_names import build_account_detail_name_map
from plugins.endfield.account_detail_service import build_account_detail_view


class EndfieldAccountDetailNameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.name_map = build_account_detail_name_map(
            {
                "chr_1": {"charId": "chr_1", "name": {"id": 1, "text": ""}},
            },
            {
                "chr_1": {
                    "skillGroupMap": {
                        "chr_1_NormalSkill": {
                            "skillGroupId": "chr_1_NormalSkill",
                            "name": {"id": 2, "text": ""},
                            "skillIdList": ["chr_1_normal_skill"],
                        }
                    }
                }
            },
            {
                "wpn_1": {"weaponId": "wpn_1", "engName": {"id": 3, "text": ""}},
            },
            {
                "item_1": {"id": "item_1", "name": {"id": 4, "text": ""}},
                "wpn_1": {"id": "wpn_1", "name": {"id": 6, "text": ""}},
            },
            {
                "suit_1": {"list": [{"suitName": {"id": 5, "text": ""}}]},
            },
            {
                "1": "中文角色",
                "2": "普通技能",
                "3": "中文武器",
                "4": "中文装备",
                "5": "中文套装",
                "6": "物品中文武器",
            },
            version="test-version",
        )

    def test_resolves_names_from_akedata_text_ids(self):
        self.assertEqual(self.name_map.character_names["chr_1"], "中文角色")
        self.assertEqual(self.name_map.character_names[md5(b"chr_1").hexdigest()], "中文角色")
        self.assertEqual(self.name_map.skill_names["chr_1_normal_skill"], "普通技能")
        self.assertEqual(self.name_map.weapon_names["wpn_1"], "物品中文武器")
        self.assertEqual(self.name_map.item_names["item_1"], "中文装备")
        self.assertEqual(self.name_map.suit_names["suit_1"], "中文套装")

    def test_account_detail_prefers_akedata_names_over_api_names(self):
        detail = {
            "chars": [
                {
                    "id": "char-instance-1",
                    "level": 90,
                    "charData": {
                        "id": md5(b"chr_1").hexdigest(),
                        "name": "Arcane",
                        "skills": [
                            {"id": md5(b"chr_1_normal_skill").hexdigest(), "name": "Normal Skill"}
                        ],
                    },
                    "weapon": {
                        "weaponData": {
                            "id": md5(b"wpn_1").hexdigest(),
                            "name": "English Weapon",
                        },
                    },
                    "bodyEquip": {
                        "equipData": {
                            "id": md5(b"item_1").hexdigest(),
                            "name": "English Equip",
                            "suit": {
                                "id": md5(b"suit_1").hexdigest(),
                                "name": "English Suit",
                            },
                        }
                    },
                }
            ]
        }

        view = build_account_detail_view(detail, uid="uid", name_map=self.name_map)
        operator = view.operators[0]
        self.assertEqual(operator.name, "中文角色")
        self.assertEqual(operator.skills[0].name, "普通技能")
        self.assertEqual(operator.weapon.name, "物品中文武器")
        self.assertEqual(operator.equips[0].name, "中文装备")
        self.assertEqual(operator.equips[0].suit_name, "中文套装")


if __name__ == "__main__":
    unittest.main()
