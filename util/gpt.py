import openai
import requests
import time
from util.constant import SPEECH_API_TOKEN


def get_response(prompt, args, max_tokens):
    if args.speech_api:
        while 1:
            try:
                response = requests.post(
                    'https://frostsnowjh.com/v1/chat/completions',
                    json={
                        'model': args.gpt,
                        'messages': prompt,
                        'max_tokens': max_tokens,
                        'temperature': 0,
                        'top_p': 1,
                        'frequency_penalty': 0,
                        'presence_penalty': 0
                    },
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + SPEECH_API_TOKEN
                    }
                ).json()
                return response['choices'][0]['message']['content']
            except:
                print('Retrying ...')
                time.sleep(10)
    while 1:
        if isinstance(prompt, str):
            pass
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
