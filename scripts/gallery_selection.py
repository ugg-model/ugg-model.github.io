"""Select high-scoring cases within capped, balanced dataset quotas."""
from collections import Counter, defaultdict
import math


RULES = {"nvs": ("psnr", "higher"), "depth": ("abs_rel", "lower"), "camera": ("ate_m", "lower")}


def balanced_quotas(capacities, target):
    """Fill the smallest dataset share first, stopping at available capacity."""
    quotas = {dataset: 0 for dataset in sorted(capacities)}
    for _ in range(min(target, sum(capacities.values()))):
        available = [dataset for dataset in quotas if quotas[dataset] < capacities[dataset]]
        dataset = min(available, key=lambda name: (quotas[name], name))
        quotas[dataset] += 1
    return quotas


def interleave(ranked_groups):
    """Weighted fair order spreads small datasets through the whole gallery."""
    sizes = {dataset: len(cases) for dataset, cases in ranked_groups.items()}
    used = Counter()
    total = sum(sizes.values())
    ordered = []
    for position in range(total):
        available = [dataset for dataset in sizes if used[dataset] < sizes[dataset]]
        # Integer deficits avoid floating-point tie differences across machines.
        dataset = min(available, key=lambda name: (-(sizes[name] * (position + 1) - used[name] * total), name))
        ordered.append(ranked_groups[dataset][used[dataset]])
        used[dataset] += 1
    return ordered


def select_cases(cases, metrics_by_source, task, limit=72, page_size=24):
    if limit < 1 or page_size < 1:
        raise ValueError("Case limit and page size must be positive")
    metric, direction = RULES[task]
    groups = defaultdict(list)
    scores = {}
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Candidate IDs must be unique")
    for case in cases:
        value = metrics_by_source[case["source"]].get(metric)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Missing/invalid {metric} for {case['source']}")
        scores[case["id"]] = value
        groups[case["dataset"]].append(case)
    capacities = {dataset: len(group) for dataset, group in groups.items()}
    quotas = balanced_quotas(capacities, limit)
    selected = {}
    for dataset, group in groups.items():
        group.sort(key=lambda case: ((-1 if direction == "higher" else 1) * scores[case["id"]], case["id"]))
        selected[dataset] = group[:quotas[dataset]]
    ordered = interleave(selected)
    metric_name = {"psnr": "PSNR", "abs_rel": "AbsRel", "ate_m": "ATE"}[metric]
    if len(ordered) == len(cases):
        caption = f"All {len(ordered)} available clips, ordered by {metric_name} within datasets and mixed across pages."
    else:
        caption = f"{len(ordered)} showcase clips selected by {'highest' if direction == 'higher' else 'lowest'} {metric_name} within datasets, with balanced dataset coverage."
    return ordered, {
        "limit": limit, "available": len(cases), "selected": len(ordered), "metric": metric,
        "direction": direction, "dataset_available": dict(sorted(capacities.items())),
        "dataset_quotas": quotas, "tie_break": "case ID ascending",
        "conditioning_policy": "Rank together across conditioning settings" if task == "nvs" else "Not applicable",
        "task_independent": True, "page_size": page_size,
        "page_datasets": [dict(sorted(Counter(case["dataset"] for case in ordered[start:start + page_size]).items()))
                          for start in range(0, len(ordered), page_size)],
        "cutoff_scores": {dataset: scores[group[-1]["id"]] for dataset, group in sorted(selected.items()) if group},
        "caption": caption,
    }
