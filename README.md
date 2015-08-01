# aiothrottle
Throttled flow controlling StreamReader for aiohttp

#Usage:
```python
import functools
import aiohttp
import aiothrottle

kbps = 200
partial = functools.partial(
    aiothrottle.ThrottledStreamReader, rate_limit=kbps * 1024)
aiohttp.client_reqrep.ClientResponse.flow_control_class = partial
```
