GPT_CHAT_MODELS = ['gpt-3.5-turbo', 'gpt-3.5-turbo-16k', 'gpt-4']

GPT_COMPLETION_MODELS = ['code-davinci-002', 'text-davinci-003']

MAX_LENS = {
    'gpt-3.5-turbo': 7000,
    'gpt-3.5-turbo-16k': 28000,
    'gpt-4': 14000,
    'code-davinci-002': 14000,
    'text-davinci-003': 7000
}

SPEECH_API_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJoY3o5OSIsImlhdCI6MTY3OTY0Nzc0NywiZXhwIjoxNjgyMjM5NzQ3LCJuYW1lX2NuIjoiXHU1ZjIwXHU2NjU3XHU3ZmMwIiwidXNlcm5hbWUiOiJoY3o5OSIsIm9yZyI6InNqdHUifQ.AYi6YCKqgRoSUbDFaDWH25RwVri79BlFiaPsDDvLXNs'

AGGS = [None, 'MAX', 'MIN', 'COUNT', 'SUM', 'AVG']

COND_OPS = [None, 'BETWEEN', '=', '>', '<', '>=', '<=', '!=', 'IN', 'LIKE', 'IS']

OPS = [None, '-', '+', '*', '/']

SET_OPS = ['intersect', 'union', 'except']

EDIT_RULES = [
    'EditIUE',
    'EditFromTable',
    'EditJoinCondition',
    'EditJoinLogicalOperator',
    'EditNestedFromClause',
    'EditSelectItem',
    'EditWhereCondition',
    'EditWhereLogicalOperator',
    'EditGroupByColumn',
    'EditHavingCondition',
    'EditHavingLogicalOperator',
    'EditOrderByItem',
    'EditOrder',
    'EditLimit',
    'TakeAsNestedFromClause',
    'OnlyRetainNestedFromClause',
    'TakeAsNestedCondition',
    'OnlyRetainNestedCondition'
]
