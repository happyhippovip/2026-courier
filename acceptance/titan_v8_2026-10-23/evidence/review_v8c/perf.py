import time,sys
from courier_core.provider_cli_guard import *
for n in [10_000, 50_000, 100_000, 200_000]:
    for s in ['x'*n, 'a '*(n//2), '"'+'x'*n, 'python -c "' + 'x'*n + '"', ';'*n]:
        t=time.time(); provider_in_script(s); print(n, repr(s[:12]), round(time.time()-t,3), flush=True)
