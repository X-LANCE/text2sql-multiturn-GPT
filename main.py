import os
import random
import time
from eval.evaluation import isValidSQL
from util.arg import main_args
from util.constant import GPT_CHAT_MODELS, GPT_COMPLETION_MODELS
from util.example import Example
from util.gpt import get_response
from util.prompt import PromptMaker


def postprocess(response, args, db_id=None):
    if args.gpt in GPT_CHAT_MODELS:
        start_idx = response.find('SELECT')
        if start_idx < 0:
            start_idx = response.find('select')
            if start_idx < 0:
                return response
        original_sql = response[start_idx:]
        end_idx = original_sql.find('```')
        if end_idx >= 0:
            original_sql = original_sql[:end_idx]
    elif args.gpt in GPT_COMPLETION_MODELS:
        original_sql = 'SELECT ' + response
    else:
        raise ValueError(f'unknown GPT model {args.gpt}')
    original_sql = ' '.join(original_sql.replace('==', '=').replace('<>', '!=').split())
    original_sql = original_sql.replace('INNER JOIN', 'JOIN').replace('inner join', 'join')
    original_sql = original_sql.replace('LEFT JOIN', 'JOIN').replace('left join', 'join')
    if db_id is None:
        return original_sql
    sql = original_sql
    while len(sql) > 0 and not isValidSQL(sql, os.path.join(Example.evaluator.db_dir, db_id, db_id + '.sqlite')):
        sql = ' '.join(sql.split()[:-1])
    return sql if len(sql) > 0 else original_sql


def decode(train_dataset, dev_dataset, args, etype='all'):
    prompt_maker = PromptMaker(args=args)
    shots = prompt_maker.get_shots(train_dataset, args)
    if not os.path.exists(args.log_path):
        os.makedirs(args.log_path)
    pred_filename = os.path.join(args.log_path, 'pred.sql')
    if os.path.exists(pred_filename):
        with open(pred_filename, 'r', encoding='utf-8') as pred_file:
            cached = pred_file.read().count('\n\n') + 1
        pred_file = open(pred_filename, 'a', encoding='utf-8')
    else:
        cached = 0
        pred_file = open(pred_filename, 'w', encoding='utf-8')
    for i, example in enumerate(dev_dataset):
        if i < cached:
            continue
        if i > 0:
            pred_file.write('\n')
            pred_file.flush()
        db_id = example['database_id']
        interaction = []
        for j, turn in enumerate(example['interaction']):
            print(f'Decoding example {i}-{j} ...')
            interaction.append({'utterance': turn['utterance']})
            response = get_response(prompt_maker.get_prompt(args, db_id, interaction, shots), args)
            sql = postprocess(response, args, db_id)
            interaction[-1]['query'] = sql
            pred_file.write(sql + '\n')
            pred_file.flush()
    pred_file.close()
    return Example.evaluator.accuracy(pred_filename, dev_dataset, os.path.join(args.log_path, 'dev.txt'), etype=etype)


args = main_args()
random.seed(args.seed)
Example.configuration(args.dataset)
start_time = time.time()
train_dataset = Example.load_dataset(args.dataset, 'train')
dev_dataset = Example.load_dataset(args.dataset, 'dev')
print(f'Dataset size: train -> {len(train_dataset):d}, dev -> {len(dev_dataset):d} ;')
print(f'Load dataset finished, cost {time.time() - start_time:.4f}s ;')
Example.use_database_testsuite()
print('Start evaluating dev dataset on testsuite database ...')
start_time = time.time()
dev_em_acc, dev_ex_acc = decode(train_dataset, dev_dataset, args)
print(f'Evaluation costs {time.time() - start_time:.2f}s, Dev EM/EXT acc: {dev_em_acc:.4f}/{dev_ex_acc:.4f} ;')
