import argparse
import os


def main_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--dataset', default='sparc', type=str, help='dataset name')
    arg_parser.add_argument('--gpt', default='gpt-3.5-turbo', type=str, help='GPT model')
    arg_parser.add_argument('--seed', default=42, type=int, help='random seed')
    arg_parser.add_argument('--api_doc', action='store_true', help='write schema according to api doc')
    arg_parser.add_argument('--pf', default='eot', type=str, choices=['no', 'eoc', 'eot'], help='format of primary and foreign keys')
    arg_parser.add_argument('--content', default=3, type=int, help='number of database records')
    arg_parser.add_argument('--shot_num', default=4, type=int, help='number of shots')
    arg_parser.add_argument('--speech_api', action='store_true', help='use speech api')
    args = arg_parser.parse_args()
    args.log_path = args.gpt
    args.log_path += '__seed_' + str(args.seed)
    if args.api_doc:
        args.log_path += '__api_doc'
    args.log_path += '__' + args.pf + '_pf'
    args.log_path += '__content_' + str(args.content)
    args.log_path += '__shot_num_' + str(args.shot_num)
    args.log_path = os.path.join('log', args.dataset, args.log_path)
    return args
