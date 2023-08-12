import json
import openai
import requests
import time
from util.constant import SPEECH_API_TOKEN


def get_response(prompt, args, max_tokens):
    if args.speech_api:
        post_data = {
            'model': args.gpt,
            'max_tokens': max_tokens,
            'temperature': 0,
            'top_p': 1,
            'frequency_penalty': 0,
            'presence_penalty': 0
        }
        if isinstance(prompt, str):
            url = 'http://54.193.55.85:10030/v1/completions?use_cache=false'
            post_data['prompt'] = prompt
            post_data['stop'] = [';', '\n\n', 'Given', 'Question', 'Translate']
        else:
            url = 'http://54.193.55.85:10030/v1/completions/chat?use_cache=false'
            post_data['messages'] = prompt
        while 1:
            try:
                response = json.loads(requests.post(url, json=post_data, headers={'llm-token': SPEECH_API_TOKEN}).text)
                print('Daily left token num:', response['daily_left_token_num'])
                result = response['result']
                return result['text'] if isinstance(prompt, str) else result['message']['content']
            except:
                print('Retrying ...')
                time.sleep(10)
    while 1:
        if isinstance(prompt, str):
            try:
                response = openai.Completion.create(
                    model=args.gpt,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=0,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0,
                    stop=[';', '\n\n', 'Given', 'Question', 'Translate']
                )
                return response['choices'][0]['text']
            except Exception as e:
                if str(e).startswith("This model's maximum context length is"):
                    return None
                print('Retrying ...')
                time.sleep(10)
        else:
            try:
                response = openai.ChatCompletion.create(
                    model=args.gpt,
                    messages=prompt,
                    max_tokens=max_tokens,
                    temperature=0,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0
                )
                return response['choices'][0]['message']['content']
            except Exception as e:
                if str(e).startswith("This model's maximum context length is"):
                    return None
                print('Retrying ...')
                time.sleep(10)
