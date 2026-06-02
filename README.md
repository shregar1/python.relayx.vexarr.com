# RelayX Python SDK

```python
from relayx import RelayXClient

client = RelayXClient(api_key="rx_...")
response = client.chat_completions({
    "model": "code-model",
    "messages": [{"role": "user", "content": "Review this diff"}],
})
```
