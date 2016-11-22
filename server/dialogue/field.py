from collections import namedtuple, defaultdict

from math import log


def select(selector_path):
    def sel(raw_entry: object) -> object:
        nonlocal selector_path
        sub = raw_entry
        for s in selector_path:
            sub = sub[s]
        return sub

    return sel


class Field:
    def __init__(self,
                 name: str,
                 selector,
                 categorize=lambda x: x,
                 score: float = 1,
                 default_value: object = None):
        self.name = name
        self.data = []
        self.categorize = categorize
        if isinstance(selector, list):
            self.selector = select(selector)
        else:
            self.selector = selector
        self.score = score
        self.default_value = default_value

    # Returns the category name and attribute value if the data_entry matches
    # a Field category. Returns (None, None) otherwise.
    def filter(self, data_entry: object) -> (str, object):
        selected = self.selector(data_entry)
        category = self.categorize(selected)
        return category, selected

    # updates self.data with only the field's column and filter raw_data
    # by returning a bool array
    # TODO revise so that we can filter Manager.possible_values using selected categories
    def update(self, raw_data: [object]) -> [bool]:
        result = []
        self.data.clear()
        for entry in raw_data:
            f = self.filter(entry)
            if f is None:
                result.append(False)
            else:
                result.append(True)
                self.data.append(f)

        return result

    def category_count(self, raw_data: [object]) -> {str: int}:
        attributes = defaultdict(int)
        for entry in raw_data:
            cat, _ = self.filter(entry)
            if cat is not None:
                if isinstance(cat, list):
                    for sub_cat in cat:
                        attributes[str(sub_cat)] += 1
                elif isinstance(cat, dict):
                    for key, value in cat.items():
                        attributes["%s=%s" % (str(key), str(value))] += 1
                else:
                    attributes[cat] += 1
        return attributes

    def entropy(self, raw_data: [object]) -> float:
        attributes = self.category_count(raw_data)
        e = 0
        for _, count in attributes.items():
            fraction = count / len(raw_data)
            e -= fraction * log(fraction)

        return e * self.score

    def gini(self, raw_data: [object]) -> float:
        return 0

    def print_stats(self, raw_data: [object]):
        print("Attribute %s" % self.name)
        print("\tEntropy:    %.6f" % self.entropy(raw_data))
        cat_counts = sorted(list(self.category_count(raw_data).items()), key=lambda x: x[0])
        print("\tCategories: %i" % len(cat_counts))
        print("\tCounts:     %s" % ", ".join("%s: %i" % (category, count) for category, count in cat_counts))

    # only select values with highest score
    def prune(self, values: [(str, float)]) -> [(str, float)]:
        # perform MeanShift clustering
        from sklearn.cluster import MeanShift, estimate_bandwidth
        import numpy as np

        scores = [score for _, score in values]
        X = np.array(list(zip(scores, np.zeros(len(scores)))), dtype=np.float)
        bandwidth = estimate_bandwidth(X, quantile=0.1)
        ms = MeanShift(bandwidth=bandwidth, bin_seeding=True)
        ms.fit(X)
        labels = ms.labels_

        labels_unique = np.unique(labels)
        n_clusters_ = len(labels_unique)

        ms_clusters = []
        for k in range(n_clusters_):
            my_members = labels == k
            print("cluster %i: %s" % (k, str(X[my_members, 0])))
            ms_clusters.append(X[my_members, 0])

        max_cluster = ms_clusters[0]
        for c in ms_clusters[1:]:
            if max(c) > max(max_cluster):
                max_cluster = c

        return list(filter(lambda x: x[1] >= min(max_cluster), values))


NumCategory = namedtuple("NumCategory", ["name", "lb", "ub"])


class NumField(Field):
    def __init__(self,
                 name: str,
                 selector_path: [str],
                 categories: [NumCategory],
                 parse_value=lambda x: x,
                 score: float = 1,
                 default_value: float = 0):
        super().__init__(name, selector_path, self.categorize, score, default_value)
        self.categories = categories
        self.parse_value = parse_value

    def categorize(self, selected: str) -> str:
        selected = self.parse_value(selected)
        for category in self.categories:
            if category.lb <= selected <= category.ub:
                return category.name
        return None
