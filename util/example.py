import json
import os
import pickle
from eval.evaluator import Evaluator


class Example:
    @classmethod
    def configuration(cls, dataset):
        cls.dataset_dir = os.path.join('data', dataset)
        cls.evaluator = Evaluator(os.path.join(cls.dataset_dir, 'tables.json'), os.path.join(cls.dataset_dir, 'database'))

    @classmethod
    def load_dataset(cls, dataset_name, choice):
        assert choice in ['train', 'dev']
        if os.path.exists(os.path.join('data', dataset_name, choice + '.bin')):
            with open(os.path.join('data', dataset_name, choice + '.bin'), 'rb') as file:
                dataset = pickle.load(file)
        else:
            with open(os.path.join('data', dataset_name, choice + '.json'), 'r', encoding='utf-8') as file:
                dataset = json.load(file)
        return dataset

    @classmethod
    def use_database_testsuite(cls):
        cls.evaluator.change_database(os.path.join(cls.dataset_dir, 'database-testsuite'))
