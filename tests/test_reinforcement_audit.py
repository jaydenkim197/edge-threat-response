import unittest

from edge_threat_response.dataset.reinforcement_audit import candidate_links


class ReinforcementLinkTests(unittest.TestCase):
    def test_cross_source_family_and_unselected_bridge_protect_holdout(self):
        full = [{"record_id":p,"dataset_id":"sohas","image_sha256":h} for p,h in
                [("images/room001.jpg","val"),("images/bridge.jpg","bridge"),("images/dsc_001.jpg","train")]]
        review = [{"record_id":"dasci/1","dataset_id":"dasci-unique","image_path":"images/dsc_002.jpg","image_sha256":"new"},
                  {"record_id":"sim/1","dataset_id":"simuletic","image_path":"images/room002.jpg","image_sha256":"synthetic"}]
        links = candidate_links(review, full, [{"left":"images/room001.jpg","right":"images/bridge.jpg"}],
                                [{"left":"images/bridge.jpg","right":"images/dsc_001.jpg"}], {"val"})
        self.assertTrue(links["dasci/1"])
        self.assertFalse(links["sim/1"])
        direct = candidate_links(review, full, [{"left":"images/room001.jpg","right":"images/bridge.jpg"}],
                                 [{"left":"images/bridge.jpg","right":"images/dsc_001.jpg"}], {"val"}, candidate_families=False)
        self.assertFalse(direct["dasci/1"])

    def test_missing_protected_hash_and_unbound_pairs_fail(self):
        full = [{"record_id":"x.jpg","dataset_id":"sohas","image_sha256":"x"}]
        with self.assertRaisesRegex(ValueError,"missing"):
            candidate_links([],full,[],[],{"missing"})
        with self.assertRaisesRegex(ValueError,"outside"):
            candidate_links([],full,[],[{"left":"x.jpg","right":"missing"}],{"x"})
