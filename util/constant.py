GPT_CHAT_MODELS = ['gpt-3.5-turbo', 'gpt-4']

GPT_COMPLETION_MODELS = ['code-davinci-002', 'text-davinci-003']

MAX_LENS = {
    'gpt-3.5-turbo': 7500,
    'gpt-4': 15000,
    'code-davinci-002': 15000,
    'text-davinci-003': 7500
}

SPEECH_API_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJoY3o5OSIsImlhdCI6MTY3OTY0Nzc0NywiZXhwIjoxNjgyMjM5NzQ3LCJuYW1lX2NuIjoiXHU1ZjIwXHU2NjU3XHU3ZmMwIiwidXNlcm5hbWUiOiJoY3o5OSIsIm9yZyI6InNqdHUifQ.AYi6YCKqgRoSUbDFaDWH25RwVri79BlFiaPsDDvLXNs'

AGGS = [None, 'MAX', 'MIN', 'COUNT', 'SUM', 'AVG']

COND_OPS = [None, 'BETWEEN', '=', '>', '<', '>=', '<=', '!=', 'IN', 'LIKE', 'IS']

OPS = [None, '-', '+', '*', '/']

SET_OPS = ['intersect', 'union', 'except']
