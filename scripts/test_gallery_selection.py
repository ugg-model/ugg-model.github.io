"""Selection invariants: metric direction, capacity, ties, and page coverage."""
import unittest

from gallery_selection import balanced_quotas, select_cases


class GallerySelectionTests(unittest.TestCase):
    def catalog(self, capacities, metric="psnr"):
        cases, metrics = [], {}
        for dataset, count in capacities.items():
            for index in range(count):
                source = f"{dataset}/{index:03d}"
                case = {"id": source, "dataset": dataset, "source": source,
                        "protocol": "ncf1" if index % 2 else "ncf2"}
                cases.append(case)
                metrics[source] = {metric: index}
        return cases, metrics

    def test_capacity_capped_balance(self):
        self.assertEqual(balanced_quotas({"bonn": 5, "kitti": 13, "scannetpp": 48, "sintel": 14}, 72),
                         {"bonn": 5, "kitti": 13, "scannetpp": 40, "sintel": 14})

    def test_high_psnr_and_ignore_conditioning_quota(self):
        cases, metrics = self.catalog({"a": 20, "b": 20})
        for case in cases:
            metrics[case["source"]]["psnr"] += 100 if case["protocol"] == "ncf1" else 0
        selected, policy = select_cases(cases, metrics, "nvs", limit=12)
        self.assertEqual(policy["dataset_quotas"], {"a": 6, "b": 6})
        self.assertTrue(all(case["protocol"] == "ncf1" for case in selected))
        self.assertEqual({int(case["id"].split("/")[1]) for case in selected}, {9, 11, 13, 15, 17, 19})

    def test_lower_error_and_stable_ties(self):
        for task, metric in (("depth", "abs_rel"), ("camera", "ate_m")):
            cases, metrics = self.catalog({"a": 10}, metric)
            metrics["a/005"][metric] = 0
            selected, _ = select_cases(list(reversed(cases)), metrics, task, limit=3)
            self.assertEqual([case["id"] for case in selected], ["a/000", "a/005", "a/001"])

    def test_every_page_contains_every_dataset(self):
        for capacities, task, metric in (({f"d{i}": 40 for i in range(6)}, "nvs", "psnr"),
                                        ({"bonn": 5, "kitti": 13, "scannetpp": 48, "sintel": 14}, "depth", "abs_rel"),
                                        ({"bonn": 5, "scannetpp": 48, "sintel": 13}, "camera", "ate_m")):
            cases, metrics = self.catalog(capacities, metric)
            selected, policy = select_cases(cases, metrics, task)
            self.assertEqual(len(selected), min(72, sum(capacities.values())))
            self.assertEqual(len({case["id"] for case in selected}), len(selected))
            self.assertEqual(len(policy["page_datasets"]), 3)
            self.assertTrue(all(set(page) == set(capacities) for page in policy["page_datasets"]))
            if task == "nvs":
                self.assertTrue(all(set(page.values()) == {4} for page in policy["page_datasets"]))

    def test_invalid_scores_fail_instead_of_guessing(self):
        cases, metrics = self.catalog({"a": 1})
        for value in (None, True, float("nan"), float("inf")):
            metrics["a/000"]["psnr"] = value
            with self.assertRaises(ValueError):
                select_cases(cases, metrics, "nvs")


if __name__ == "__main__":
    unittest.main()
